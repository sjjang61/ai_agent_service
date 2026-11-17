"""Drive 서비스: 폴더 트리·파일 저장·이동·휴지통·용량. 모든 접근은 get_owned() 한 곳을 지나며 user_id 가 다르면 '없음'(404)으로 응답한다.

파일 본문은 drive_storage(MinIO)에, 구조·이름·크기는 DB(drive_nodes)에 둔다. 폴더 깊이가 DRIVE_MAX_DEPTH(기본 20) 이하라서
트리 탐색은 재귀 CTE 대신 한 층씩 올라가거나 내려가는 단순한 질의로 한다 (DB 종류와 무관하게 동작한다).
"""
import mimetypes
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import BinaryIO, Optional

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.config import settings
from app.models.drive import DriveNode, DriveUsage
from app.services import drive_storage
from app.services.artifact_service import classify

ROOT_NAME = "Drive"
_BAD_NAME = re.compile(r"[\x00-\x1f\x7f/\\]")
_IN_CHUNK = 500


class DriveError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 오류. status 는 HTTP 상태."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB 는 naive UTC


def quota_bytes() -> int:
    return int(settings.DRIVE_QUOTA_GB * 1024 * 1024 * 1024)


def max_file_bytes() -> int:
    return settings.DRIVE_MAX_FILE_MB * 1024 * 1024


# ── 이름 ──────────────────────────────────────────────────────
def normalize_name(raw: str) -> str:
    """NFC 정규화(macOS 는 한글 파일명을 NFD 로 올린다) + 검증. 같은 이름이 둘로 보이는 일을 막는다."""
    name = unicodedata.normalize("NFC", raw or "").strip()
    if not name:
        raise DriveError(400, "이름을 입력하세요")
    if len(name) > 255:
        raise DriveError(400, "이름은 255자 이하여야 합니다")
    if name in (".", "..") or _BAD_NAME.search(name):
        raise DriveError(400, "이름에 사용할 수 없는 문자가 있습니다 ( / \\ 및 제어문자, '.' '..')")
    return name


def _key(name: str) -> str:
    return name.casefold()


def unique_name(name: str, taken: set) -> str:
    """같은 이름이 있으면 '이름 (1).확장자' 로 번호를 붙인다. taken 은 casefold 된 이름 집합."""
    if _key(name) not in taken:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:  # 확장자 없음 또는 .env 같은 점 파일
        stem, ext = name, ""
    for i in range(1, 10000):
        cand = f"{stem} ({i}){'.' + ext if ext else ''}"
        if _key(cand) not in taken:
            return cand
    raise DriveError(409, "같은 이름의 항목이 너무 많습니다")


def guess_mime(name: str) -> str:
    kind, mime = classify(name)
    return mime or mimetypes.guess_type(name)[0] or "application/octet-stream"


# ── 조회 ──────────────────────────────────────────────────────
async def ensure_root(db: AsyncSession, user_id: str) -> DriveNode:
    """사용자 루트 폴더(id == user_id)를 돌려준다. 없으면 만든다 (동시에 만들어도 하나만 남는다)."""
    root = await db.get(DriveNode, user_id)
    if root is not None:
        return root
    db.add(DriveNode(id=user_id, user_id=user_id, parent_id=None, type="folder", name=ROOT_NAME, source="upload"))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
    return await db.get(DriveNode, user_id)


async def get_owned(db: AsyncSession, user_id: str, node_id: str, *, trashed: Optional[bool] = False) -> DriveNode:
    """내 노드만 돌려준다. 없거나 남의 것이면 같은 404. trashed=False 는 살아 있는 것만, True 는 휴지통만, None 은 둘 다."""
    if node_id in ("root", "", None):
        node_id = user_id
    node = await db.get(DriveNode, node_id, populate_existing=True)  # 같은 세션에서 벌크 UPDATE 를 한 뒤에도 항상 최신 값을 읽는다
    if node is None or node.user_id != user_id:
        raise DriveError(404, "항목을 찾을 수 없습니다")
    if node.id == user_id and node.parent_id is None:
        return node
    if trashed is False and node.trashed_at is not None:
        raise DriveError(404, "항목을 찾을 수 없습니다")
    if trashed is True and node.trashed_at is None:
        raise DriveError(404, "항목을 찾을 수 없습니다")
    return node


async def get_folder(db: AsyncSession, user_id: str, node_id: str) -> DriveNode:
    node = await ensure_root(db, user_id) if node_id in ("root", "", None, user_id) else await get_owned(db, user_id, node_id)
    if node.type != "folder":
        raise DriveError(400, "폴더가 아닙니다")
    return node


async def chain(db: AsyncSession, node: DriveNode) -> list:
    """루트부터 node 까지의 경로 (루트 포함). 깊이 한도보다 길면 데이터가 잘못된 것이므로 끊는다."""
    out, cur, guard = [node], node, 0
    while cur.parent_id is not None and guard <= settings.DRIVE_MAX_DEPTH + 5:
        cur = await db.get(DriveNode, cur.parent_id, populate_existing=True)
        if cur is None:
            break
        out.append(cur)
        guard += 1
    return list(reversed(out))


def depth_of(path_chain: list) -> int:
    return len(path_chain) - 1  # 루트는 0


async def node_path(db: AsyncSession, node: DriveNode) -> str:
    names = [n.name for n in (await chain(db, node))[1:]]
    return "/" + "/".join(names)


async def _live_names(db: AsyncSession, user_id: str, parent_id: str) -> set:
    rows = (await db.execute(select(DriveNode.name).where(DriveNode.user_id == user_id, DriveNode.parent_id == parent_id, DriveNode.trashed_at.is_(None)))).scalars().all()
    return {_key(n) for n in rows}


async def _child_count(db: AsyncSession, user_id: str, parent_id: str) -> int:
    return (await db.execute(select(func.count()).select_from(DriveNode).where(DriveNode.user_id == user_id, DriveNode.parent_id == parent_id, DriveNode.trashed_at.is_(None)))).scalar() or 0


async def list_children(db: AsyncSession, user_id: str, parent: DriveNode, sort: str = "name", desc: bool = False, cursor: int = 0, limit: int = 500, folders_only: bool = False) -> tuple[list, Optional[int]]:
    """폴더 내용 (폴더 먼저). 큰 JSON 열(source_ref)은 읽지 않는다. 반환: (노드들, 다음 cursor 또는 None)"""
    limit = max(1, min(limit, 1000))
    col = {"name": func.lower(DriveNode.name), "size": DriveNode.size_bytes, "updated": DriveNode.updated_at}.get(sort, func.lower(DriveNode.name))
    order = col.desc() if desc else col.asc()
    q = (
        select(DriveNode).options(defer(DriveNode.source_ref))
        .where(DriveNode.user_id == user_id, DriveNode.parent_id == parent.id, DriveNode.trashed_at.is_(None))
        .order_by(case((DriveNode.type == "folder", 0), else_=1), order, DriveNode.id)
        .offset(max(0, cursor)).limit(limit + 1)
    )
    if folders_only:
        q = q.where(DriveNode.type == "folder")
    rows = list((await db.execute(q)).scalars().all())
    nxt = cursor + limit if len(rows) > limit else None
    return rows[:limit], nxt


async def find_child(db: AsyncSession, user_id: str, parent_id: str, name: str) -> Optional[DriveNode]:
    """parent 폴더 안의 살아 있는 항목을 이름(대소문자·NFC 무시)으로 찾는다."""
    n = unicodedata.normalize("NFC", name or "")
    return (await db.execute(
        select(DriveNode).options(defer(DriveNode.source_ref))
        .where(DriveNode.user_id == user_id, DriveNode.parent_id == parent_id, DriveNode.trashed_at.is_(None), func.lower(DriveNode.name) == n.lower())
    )).scalars().first()


async def ensure_folder_path(db: AsyncSession, user_id: str, path: str) -> DriveNode:
    """'/보고서/2026' 폴더를 돌려준다. 없는 단계는 만든다. 같은 이름의 파일이 있으면 409."""
    cur = await ensure_root(db, user_id)
    for part in [p for p in unicodedata.normalize("NFC", path or "").split("/") if p]:
        nxt = await find_child(db, user_id, cur.id, part)
        if nxt is None:
            nxt = await create_folder(db, user_id, cur.id, part)
        elif nxt.type != "folder":
            raise DriveError(409, f"'{part}' 은(는) 폴더가 아니라 파일입니다")
        cur = nxt
    return cur


async def resolve(db: AsyncSession, user_id: str, path: str) -> Optional[DriveNode]:
    """'/보고서/요약.pdf' 형식의 경로를 노드로. 이름은 대소문자·NFC 를 구분하지 않고 비교한다. 없으면 None."""
    cur = await ensure_root(db, user_id)
    for part in [p for p in unicodedata.normalize("NFC", path or "").split("/") if p]:
        nxt = (await db.execute(
            select(DriveNode).options(defer(DriveNode.source_ref))
            .where(DriveNode.user_id == user_id, DriveNode.parent_id == cur.id, DriveNode.trashed_at.is_(None), func.lower(DriveNode.name) == part.lower())
        )).scalars().first()
        if nxt is None:
            return None
        cur = nxt
    return cur


# ── 용량 ──────────────────────────────────────────────────────
async def usage(db: AsyncSession, user_id: str) -> dict:
    used = (await db.execute(select(DriveUsage.used_bytes).where(DriveUsage.user_id == user_id))).scalar() or 0
    return {"used_bytes": int(used), "quota_bytes": quota_bytes()}


async def _reserve(db: AsyncSession, user_id: str, nbytes: int) -> None:
    """용량을 먼저 선점한다 (조건부 UPDATE 라서 동시 업로드가 한도를 함께 넘지 못한다). 업로드가 실패하면 _release 로 돌려준다."""
    if (await db.execute(select(DriveUsage.user_id).where(DriveUsage.user_id == user_id))).first() is None:
        db.add(DriveUsage(user_id=user_id, used_bytes=0))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    r = await db.execute(update(DriveUsage).where(DriveUsage.user_id == user_id, DriveUsage.used_bytes + nbytes <= quota_bytes()).values(used_bytes=DriveUsage.used_bytes + nbytes))
    await db.commit()
    if (r.rowcount or 0) == 0:
        raise DriveError(413, f"Drive 용량 한도({settings.DRIVE_QUOTA_GB:g}GB)를 넘습니다. 파일을 삭제하거나 휴지통을 비우세요")


async def _release(db: AsyncSession, user_id: str, nbytes: int) -> None:
    if nbytes <= 0:
        return
    left = DriveUsage.used_bytes - nbytes
    await db.execute(update(DriveUsage).where(DriveUsage.user_id == user_id).values(used_bytes=case((left < 0, 0), else_=left)))  # 음수가 되지 않게
    await db.commit()


# ── 만들기 ────────────────────────────────────────────────────
async def create_folder(db: AsyncSession, user_id: str, parent_id: str, name: str, source: str = "upload") -> DriveNode:
    parent = await get_folder(db, user_id, parent_id)
    name = normalize_name(name)
    pchain = await chain(db, parent)
    if depth_of(pchain) + 1 > settings.DRIVE_MAX_DEPTH:
        raise DriveError(400, f"폴더는 {settings.DRIVE_MAX_DEPTH}단계까지만 만들 수 있습니다")
    if await _child_count(db, user_id, parent.id) >= settings.DRIVE_MAX_CHILDREN:
        raise DriveError(400, f"한 폴더에는 {settings.DRIVE_MAX_CHILDREN}개까지만 둘 수 있습니다")
    if _key(name) in await _live_names(db, user_id, parent.id):
        raise DriveError(409, f"같은 이름의 항목이 이미 있습니다: {name}")
    node = DriveNode(user_id=user_id, parent_id=parent.id, type="folder", name=name, source=source)
    db.add(node)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DriveError(409, f"같은 이름의 항목이 이미 있습니다: {name}")
    return node


async def create_file(
    db: AsyncSession, user_id: str, parent_id: str, name: str, src: BinaryIO, size: int, sha256: str,
    mime: Optional[str] = None, source: str = "upload", source_ref: Optional[dict] = None, store=None,
) -> DriveNode:
    """src(이미 크기·해시를 센 임시 파일)를 Drive 에 저장한다. 같은 이름이 있으면 번호를 붙인다(덮어쓰지 않는다).
    순서: 용량 선점 → 객체 저장 → DB 행. 어느 단계에서 실패해도 객체와 선점한 용량을 되돌린다."""
    store = store or drive_storage.storage
    pid = (await get_folder(db, user_id, parent_id)).id  # 값만 꺼내 둔다: 아래 rollback()(동시 첫 업로드의 용량 행 충돌 등)이 세션 객체를 만료시킨다
    name = normalize_name(name)
    if size > max_file_bytes():
        raise DriveError(413, f"파일은 {settings.DRIVE_MAX_FILE_MB}MB 까지 올릴 수 있습니다")
    if await _child_count(db, user_id, pid) >= settings.DRIVE_MAX_CHILDREN:
        raise DriveError(400, f"한 폴더에는 {settings.DRIVE_MAX_CHILDREN}개까지만 둘 수 있습니다")

    await _reserve(db, user_id, size)
    node_id = str(uuid.uuid4())
    key = drive_storage.make_key(user_id, node_id)
    stored = False
    try:
        try:
            await store.put(key, src, size, mime or guess_mime(name))
        except Exception as e:  # noqa: BLE001
            raise DriveError(502, f"저장소에 쓰지 못했습니다: {type(e).__name__}")
        stored = True
        taken = await _live_names(db, user_id, pid)
        for _ in range(5):  # 같은 이름을 동시에 올리면 번호가 겹칠 수 있어 몇 번 더 시도한다
            final = unique_name(name, taken)
            node = DriveNode(
                id=node_id, user_id=user_id, parent_id=pid, type="file", name=final, size_bytes=size, mime=mime or guess_mime(final),
                sha256=sha256, storage_key=key, source=source, source_ref=source_ref,
            )
            db.add(node)
            try:
                await db.commit()
                return node
            except IntegrityError:
                await db.rollback()
                taken = await _live_names(db, user_id, pid) | {_key(final)}
        raise DriveError(409, "같은 이름의 항목이 너무 많습니다")
    except BaseException:
        await db.rollback()
        if stored:
            try:
                await store.remove(key)
            except Exception:  # noqa: BLE001  남은 객체는 대조 작업이 정리한다
                pass
        await _release(db, user_id, size)
        raise


# ── 이름 변경·이동 ────────────────────────────────────────────
async def rename(db: AsyncSession, user_id: str, node_id: str, name: str) -> DriveNode:
    node = await get_owned(db, user_id, node_id)
    if node.parent_id is None:
        raise DriveError(400, "루트 폴더는 이름을 바꿀 수 없습니다")
    name = normalize_name(name)
    if name == node.name:
        return node
    taken = await _live_names(db, user_id, node.parent_id)
    taken.discard(_key(node.name))  # 대소문자만 바꾸는 경우(a.txt → A.txt)를 허용
    if _key(name) in taken:
        raise DriveError(409, f"같은 이름의 항목이 이미 있습니다: {name}")
    node.name = name
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DriveError(409, f"같은 이름의 항목이 이미 있습니다: {name}")
    return node


async def _children_of(db: AsyncSession, user_id: str, parent_ids: list, folders_only: bool = False, live_only: bool = True) -> list:
    out = []
    for i in range(0, len(parent_ids), _IN_CHUNK):
        q = select(DriveNode).options(defer(DriveNode.source_ref)).where(DriveNode.user_id == user_id, DriveNode.parent_id.in_(parent_ids[i:i + _IN_CHUNK]))
        if folders_only:
            q = q.where(DriveNode.type == "folder")
        if live_only:
            q = q.where(DriveNode.trashed_at.is_(None))
        out.extend((await db.execute(q)).scalars().all())
    return out


async def _subtree(db: AsyncSession, user_id: str, top: DriveNode, live_only: bool = True) -> list:
    """top 과 모든 하위 노드 (깊이 한도만큼 한 층씩 내려간다)."""
    found, level = [top], [top.id]
    for _ in range(settings.DRIVE_MAX_DEPTH + 5):
        kids = await _children_of(db, user_id, level, live_only=live_only)
        if not kids:
            break
        found.extend(kids)
        level = [k.id for k in kids if k.type == "folder"]
        if not level:
            break
    return found


async def _height(db: AsyncSession, user_id: str, top: DriveNode) -> int:
    """top 폴더 아래로 폴더가 몇 층 더 있는가 (파일이면 0)."""
    if top.type != "folder":
        return 0
    h, level = 0, [top.id]
    for _ in range(settings.DRIVE_MAX_DEPTH + 5):
        kids = await _children_of(db, user_id, level, folders_only=True)
        if not kids:
            break
        h += 1
        level = [k.id for k in kids]
    return h


async def move(db: AsyncSession, user_id: str, node_ids: list, parent_id: str) -> list:
    """노드들을 parent 폴더로 옮긴다. 하나라도 조건을 어기면 아무것도 옮기지 않는다."""
    parent = await get_folder(db, user_id, parent_id)
    pchain = await chain(db, parent)
    ancestors = {n.id for n in pchain}
    nodes, seen = [], set()
    for nid in node_ids:
        n = await get_owned(db, user_id, nid)
        if n.parent_id is None:
            raise DriveError(400, "루트 폴더는 옮길 수 없습니다")
        if n.id in seen or n.parent_id == parent.id:
            continue
        seen.add(n.id)
        if n.type == "folder" and n.id in ancestors:
            raise DriveError(400, f"'{n.name}' 폴더를 자기 자신이나 그 하위 폴더로 옮길 수 없습니다")
        if depth_of(pchain) + 1 + await _height(db, user_id, n) > settings.DRIVE_MAX_DEPTH:
            raise DriveError(400, f"폴더는 {settings.DRIVE_MAX_DEPTH}단계까지만 둘 수 있습니다")
        nodes.append(n)
    if not nodes:
        return []
    taken = await _live_names(db, user_id, parent.id)
    if len(taken) + len(nodes) > settings.DRIVE_MAX_CHILDREN:
        raise DriveError(400, f"한 폴더에는 {settings.DRIVE_MAX_CHILDREN}개까지만 둘 수 있습니다")
    incoming = set()
    for n in nodes:
        if _key(n.name) in taken or _key(n.name) in incoming:
            raise DriveError(409, f"대상 폴더에 같은 이름의 항목이 있습니다: {n.name}")
        incoming.add(_key(n.name))
    for n in nodes:
        n.parent_id = parent.id
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise DriveError(409, "대상 폴더에 같은 이름의 항목이 있습니다")
    return nodes


# ── 삭제(휴지통)·복원·영구 삭제 ───────────────────────────────
async def trash(db: AsyncSession, user_id: str, node_ids: list) -> int:
    """휴지통으로 옮긴다 (폴더는 하위 전체가 한 묶음). 이미 위에서 지워진 하위 항목은 건너뛴다. 반환: 처리한 최상위 항목 수."""
    done = 0
    now = _now()
    for nid in node_ids:
        try:
            node = await get_owned(db, user_id, nid)
        except DriveError:
            continue  # 같은 요청에서 상위 폴더와 함께 이미 지워졌거나 없는 항목
        if node.parent_id is None:
            raise DriveError(400, "루트 폴더는 삭제할 수 없습니다")
        ids = [n.id for n in await _subtree(db, user_id, node)]
        for i in range(0, len(ids), _IN_CHUNK):
            await db.execute(update(DriveNode).where(DriveNode.id.in_(ids[i:i + _IN_CHUNK])).values(trashed_at=now, trash_root_id=node.id, trash_key=node.id))
        await db.commit()
        done += 1
    return done


async def list_trash(db: AsyncSession, user_id: str) -> list:
    """휴지통의 최상위 항목들 (묶음의 루트)."""
    q = select(DriveNode).options(defer(DriveNode.source_ref)).where(DriveNode.user_id == user_id, DriveNode.trashed_at.is_not(None), DriveNode.trash_root_id == DriveNode.id).order_by(DriveNode.trashed_at.desc())
    return list((await db.execute(q)).scalars().all())


async def restore(db: AsyncSession, user_id: str, node_ids: list) -> list:
    """휴지통 묶음을 되살린다. 원래 폴더가 없거나 삭제된 상태면 루트로, 같은 이름이 있으면 번호를 붙인다."""
    restored = []
    for nid in node_ids:
        node = await get_owned(db, user_id, nid, trashed=True)
        if node.trash_root_id != node.id:
            raise DriveError(400, "삭제한 묶음의 최상위 항목만 복원할 수 있습니다")
        parent = await db.get(DriveNode, node.parent_id, populate_existing=True) if node.parent_id else None
        if parent is None or parent.user_id != user_id or parent.trashed_at is not None:
            parent = await ensure_root(db, user_id)
        node.name = unique_name(node.name, await _live_names(db, user_id, parent.id))
        node.parent_id = parent.id
        ids = [n.id for n in await _subtree(db, user_id, node, live_only=False)]
        await db.flush()
        for i in range(0, len(ids), _IN_CHUNK):
            await db.execute(update(DriveNode).where(DriveNode.id.in_(ids[i:i + _IN_CHUNK])).values(trashed_at=None, trash_root_id=None, trash_key=""))
        await db.commit()
        restored.append(await db.get(DriveNode, nid, populate_existing=True))
    return restored


async def _purge_nodes(db: AsyncSession, user_id: str, nodes: list, store) -> int:
    """노드들을 영구 삭제한다 (객체 → 행 → 용량 반환). 자식 행부터 지운다(자기 참조 FK). 반환: 반환한 바이트."""
    by_id = {n.id: n for n in nodes}
    freed = 0
    for n in nodes:
        if n.type == "file" and n.storage_key:
            try:
                await store.remove(n.storage_key)
            except Exception:  # noqa: BLE001  이미 없거나 일시 오류: 행은 지우고 남은 객체는 대조 작업이 정리한다
                pass
            freed += int(n.size_bytes or 0)

    def level(n):
        d, cur = 0, n
        while cur.parent_id in by_id and d < 100:
            cur, d = by_id[cur.parent_id], d + 1
        return d

    for lv in sorted({level(n) for n in nodes}, reverse=True):
        ids = [n.id for n in nodes if level(n) == lv]
        for i in range(0, len(ids), _IN_CHUNK):
            await db.execute(delete(DriveNode).where(DriveNode.id.in_(ids[i:i + _IN_CHUNK])))
    await db.commit()
    await _release(db, user_id, freed)
    return freed


async def purge(db: AsyncSession, user_id: str, node_ids: list, store=None) -> int:
    """휴지통 묶음을 영구 삭제한다. 반환: 지운 최상위 항목 수."""
    store = store or drive_storage.storage
    n = 0
    for nid in node_ids:
        node = await get_owned(db, user_id, nid, trashed=True)
        if node.trash_root_id != node.id:
            raise DriveError(400, "삭제한 묶음의 최상위 항목만 영구 삭제할 수 있습니다")
        await _purge_nodes(db, user_id, await _subtree(db, user_id, node, live_only=False), store)
        n += 1
    return n


async def empty_trash(db: AsyncSession, user_id: str, store=None) -> int:
    """휴지통을 모두 비운다. 먼저 지운 폴더 안에 이미 있던 항목처럼 앞 묶음과 함께 사라진 것은 건너뛴다."""
    store = store or drive_storage.storage
    n = 0
    for root_id in [r.id for r in await list_trash(db, user_id)]:
        root = await db.get(DriveNode, root_id, populate_existing=True)
        if root is None or root.trashed_at is None:
            continue
        await _purge_nodes(db, user_id, await _subtree(db, user_id, root, live_only=False), store)
        n += 1
    return n


async def purge_expired(db: AsyncSession, days: Optional[int] = None, store=None, limit: int = 200) -> int:
    """보관 기간이 지난 휴지통 묶음을 모든 사용자에 대해 영구 삭제한다 (주기 작업이 부른다)."""
    days = settings.DRIVE_TRASH_RETENTION_DAYS if days is None else days
    if days <= 0:
        return 0
    store = store or drive_storage.storage
    cutoff = _now() - timedelta(days=days)
    roots = (await db.execute(select(DriveNode).options(defer(DriveNode.source_ref)).where(DriveNode.trashed_at.is_not(None), DriveNode.trashed_at < cutoff, DriveNode.trash_root_id == DriveNode.id).limit(limit))).scalars().all()
    n = 0
    for r in roots:
        if await db.get(DriveNode, r.id, populate_existing=True) is None:  # 앞 묶음과 함께 이미 지워졌다
            continue
        await _purge_nodes(db, r.user_id, await _subtree(db, r.user_id, r, live_only=False), store)
        n += 1
    return n


# ── 대조(정합성) ──────────────────────────────────────────────
async def reconcile(db: AsyncSession, user_id: Optional[str] = None, store=None, fix: bool = False) -> dict:
    """DB 와 객체 저장소, 용량 카운터를 맞춰 본다.
    orphan_objects: 행이 없는 객체(업로드 도중 중단 등) / missing_objects: 객체가 없는 파일 행 / usage_drift: 카운터와 실제 합계가 다른 사용자.
    fix=True 면 orphan 객체를 지우고 카운터를 실제 합계로 고친다 (missing 은 데이터 손실이라 보고만 한다)."""
    store = store or drive_storage.storage
    prefix = f"drive/{user_id}/" if user_id else "drive/"
    keys = set(await store.list_keys(prefix))
    q = select(DriveNode.user_id, DriveNode.storage_key, DriveNode.size_bytes).where(DriveNode.type == "file")
    if user_id:
        q = q.where(DriveNode.user_id == user_id)
    rows = (await db.execute(q)).all()
    known = {r.storage_key for r in rows if r.storage_key}
    orphan = sorted(keys - known)
    missing = sorted(known - keys)
    sums: dict = {}
    for r in rows:
        sums[r.user_id] = sums.get(r.user_id, 0) + int(r.size_bytes or 0)
    drift = []
    for uid, total in sums.items():
        cur = (await db.execute(select(DriveUsage.used_bytes).where(DriveUsage.user_id == uid))).scalar()
        if cur is None or int(cur) != total:
            drift.append({"user_id": uid, "counter": None if cur is None else int(cur), "actual": total})
    if fix:
        for k in orphan:
            try:
                await store.remove(k)
            except Exception:  # noqa: BLE001
                pass
        for d in drift:
            if d["counter"] is None:
                db.add(DriveUsage(user_id=d["user_id"], used_bytes=d["actual"]))
            else:
                await db.execute(update(DriveUsage).where(DriveUsage.user_id == d["user_id"]).values(used_bytes=d["actual"]))
        await db.commit()
    return {"orphan_objects": orphan, "missing_objects": missing, "usage_drift": drift, "fixed": fix}


def node_dict(n: DriveNode) -> dict:
    return {
        "id": n.id, "type": n.type, "name": n.name, "parent_id": n.parent_id, "size_bytes": int(n.size_bytes or 0) if n.type == "file" else None,
        "mime": n.mime, "source": n.source, "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        "trashed_at": n.trashed_at.isoformat() if n.trashed_at else None,
    }

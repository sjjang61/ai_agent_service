"""Drive 서비스: 트리·이름 규칙·용량·휴지통·소유자 격리 (메모리 SQLite + 메모리 저장소, 외부 서비스 없음)"""
import hashlib
import io

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base
from app.models.drive import DriveNode, DriveUsage
from app.services import drive_service as svc
from app.services.drive_service import DriveError

A, B = "user-a-0000-0000-0000-000000000001", "user-b-0000-0000-0000-000000000002"


class MemStore:
    """MinIO 대신 쓰는 메모리 저장소 (같은 인터페이스)."""

    def __init__(self):
        self.objects: dict = {}
        self.fail_put = False

    async def put(self, key, fileobj, length, content_type="application/octet-stream"):
        if self.fail_put:
            raise OSError("boom")
        data = fileobj.read()
        assert len(data) == length
        self.objects[key] = data

    async def remove(self, key):
        self.objects.pop(key, None)

    async def list_keys(self, prefix):
        return [k for k in self.objects if k.startswith(prefix)]

    async def stream(self, key):
        data = self.objects[key]
        for i in range(0, len(data), 4):  # 작은 조각으로 흘려 보낸다
            yield data[i:i + 4]


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[DriveNode.__table__, DriveUsage.__table__]))
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def store():
    return MemStore()


async def put(db, store, user, parent, name, data=b"hello"):
    return await svc.create_file(db, user, parent, name, io.BytesIO(data), len(data), hashlib.sha256(data).hexdigest(), store=store)


# ── 이름 ──────────────────────────────────────────────────────
def test_name_normalization_and_validation():
    import unicodedata

    nfd = unicodedata.normalize("NFD", "보고서.txt")
    assert svc.normalize_name(nfd) == unicodedata.normalize("NFC", nfd)  # 한글 NFD → NFC
    assert svc.normalize_name("  a.txt  ") == "a.txt"
    for bad in ["", "   ", ".", "..", "a/b", "a\\b", "a\x00b", "x" * 256]:
        with pytest.raises(DriveError) as e:
            svc.normalize_name(bad)
        assert e.value.status == 400


def test_unique_name_numbering():
    assert svc.unique_name("a.txt", set()) == "a.txt"
    assert svc.unique_name("a.txt", {"a.txt"}) == "a (1).txt"
    assert svc.unique_name("A.TXT", {"a.txt", "a (1).txt"}) == "A (2).TXT"  # 대소문자 구분 없음
    assert svc.unique_name("README", {"readme"}) == "README (1)"
    assert svc.unique_name(".env", {".env"}) == ".env (1)"  # 점 파일은 확장자로 보지 않는다


# ── 폴더·파일 ─────────────────────────────────────────────────
async def test_root_is_created_once_and_equals_user_id(db):
    r1, r2 = await svc.ensure_root(db, A), await svc.ensure_root(db, A)
    assert r1.id == r2.id == A and r1.parent_id is None
    assert (await svc.get_owned(db, A, "root")).id == A


async def test_folder_crud_and_listing_order(db, store):
    await svc.create_folder(db, A, "root", "보고서")
    await svc.create_folder(db, A, "root", "아카이브")
    await put(db, store, A, "root", "b.txt")
    await put(db, store, A, "root", "a.txt")
    root = await svc.get_folder(db, A, "root")
    nodes, nxt = await svc.list_children(db, A, root)
    assert [n.name for n in nodes] == ["보고서", "아카이브", "a.txt", "b.txt"]  # 폴더 먼저, 이름순
    assert nxt is None
    only, _ = await svc.list_children(db, A, root, folders_only=True)
    assert [n.name for n in only] == ["보고서", "아카이브"]


async def test_duplicate_folder_name_is_conflict_case_insensitive(db):
    await svc.create_folder(db, A, "root", "Docs")
    with pytest.raises(DriveError) as e:
        await svc.create_folder(db, A, "root", "docs")
    assert e.value.status == 409


async def test_same_file_name_gets_numbered_not_overwritten(db, store):
    n1 = await put(db, store, A, "root", "r.txt", b"1")
    n2 = await put(db, store, A, "root", "r.txt", b"22")
    assert (n1.name, n2.name) == ("r.txt", "r (1).txt")
    assert store.objects[n1.storage_key] == b"1" and store.objects[n2.storage_key] == b"22"
    assert (await svc.usage(db, A))["used_bytes"] == 3


async def test_depth_limit(db, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_MAX_DEPTH", 3)
    parent = "root"
    for i in range(3):
        parent = (await svc.create_folder(db, A, parent, f"d{i}")).id
    with pytest.raises(DriveError) as e:
        await svc.create_folder(db, A, parent, "too-deep")
    assert e.value.status == 400


async def test_children_limit(db, store, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_MAX_CHILDREN", 2)
    await svc.create_folder(db, A, "root", "a")
    await svc.create_folder(db, A, "root", "b")
    with pytest.raises(DriveError):
        await svc.create_folder(db, A, "root", "c")
    with pytest.raises(DriveError):
        await put(db, store, A, "root", "x.txt")


# ── 용량 ──────────────────────────────────────────────────────
async def test_file_size_limit_and_nothing_left_behind(db, store, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_MAX_FILE_MB", 1)
    with pytest.raises(DriveError) as e:
        await svc.create_file(db, A, "root", "big.bin", io.BytesIO(b""), 2 * 1024 * 1024, "x", store=store)
    assert e.value.status == 413 and store.objects == {}


async def test_quota_is_enforced_and_released_on_failure(db, store, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_QUOTA_GB", 10 / (1024 ** 3))  # 10 바이트
    await put(db, store, A, "root", "a.txt", b"123456")
    with pytest.raises(DriveError) as e:
        await put(db, store, A, "root", "b.txt", b"123456")
    assert e.value.status == 413
    assert (await svc.usage(db, A))["used_bytes"] == 6  # 실패한 업로드가 용량을 잡고 있지 않다
    await put(db, store, A, "root", "c.txt", b"1234")  # 남은 4바이트는 쓸 수 있다
    assert (await svc.usage(db, A))["used_bytes"] == 10


async def test_storage_failure_releases_quota(db, store):
    store.fail_put = True
    with pytest.raises(DriveError) as e:
        await put(db, store, A, "root", "a.txt", b"abc")
    assert e.value.status == 502
    assert (await svc.usage(db, A))["used_bytes"] == 0
    assert (await db.execute(select(DriveNode).where(DriveNode.type == "file"))).first() is None


# ── 이름 변경·이동 ────────────────────────────────────────────
async def test_rename(db, store):
    f = await put(db, store, A, "root", "a.txt")
    await put(db, store, A, "root", "b.txt")
    assert (await svc.rename(db, A, f.id, "A.txt")).name == "A.txt"  # 대소문자만 바꾸기는 허용
    with pytest.raises(DriveError) as e:
        await svc.rename(db, A, f.id, "B.TXT")
    assert e.value.status == 409
    with pytest.raises(DriveError):
        await svc.rename(db, A, A, "x")  # 루트


async def test_move_and_cycle_prevention(db, store):
    a = await svc.create_folder(db, A, "root", "a")
    b = await svc.create_folder(db, A, a.id, "b")
    f = await put(db, store, A, "root", "f.txt")
    await svc.move(db, A, [f.id], b.id)
    assert (await svc.resolve(db, A, "/a/b/f.txt")).id == f.id
    for target in (a.id, b.id):  # 자기 자신·하위로 이동 금지
        with pytest.raises(DriveError) as e:
            await svc.move(db, A, [a.id], target)
        assert e.value.status == 400
    with pytest.raises(DriveError):
        await svc.move(db, A, [A], b.id)  # 루트 이동 금지


async def test_move_is_all_or_nothing_on_name_conflict(db, store):
    dst = await svc.create_folder(db, A, "root", "dst")
    await put(db, store, A, dst.id, "same.txt")
    x = await put(db, store, A, "root", "x.txt")
    same = await put(db, store, A, "root", "same.txt")
    with pytest.raises(DriveError) as e:
        await svc.move(db, A, [x.id, same.id], dst.id)
    assert e.value.status == 409
    assert (await svc.resolve(db, A, "/x.txt")).id == x.id  # x 도 옮겨지지 않았다


async def test_move_respects_depth_with_subtree_height(db, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_MAX_DEPTH", 3)
    a = await svc.create_folder(db, A, "root", "a")
    a1 = await svc.create_folder(db, A, a.id, "a1")
    await svc.create_folder(db, A, a1.id, "a2")  # a(1) > a1(2) > a2(3)
    z = await svc.create_folder(db, A, "root", "z")
    with pytest.raises(DriveError):
        await svc.move(db, A, [a.id], z.id)  # z(1) 아래로 가면 a2 가 4단계가 된다


# ── 휴지통 ────────────────────────────────────────────────────
async def test_trash_hides_subtree_and_restore_brings_back(db, store):
    d = await svc.create_folder(db, A, "root", "d")
    f = await put(db, store, A, d.id, "in.txt")
    assert await svc.trash(db, A, [d.id]) == 1
    assert await svc.resolve(db, A, "/d") is None
    with pytest.raises(DriveError):
        await svc.get_owned(db, A, f.id)  # 하위 파일도 숨겨진다
    assert [n.id for n in await svc.list_trash(db, A)] == [d.id]  # 묶음의 최상위만 보인다
    assert (await svc.usage(db, A))["used_bytes"] == 5  # 휴지통도 용량에 센다
    await svc.restore(db, A, [d.id])
    assert (await svc.resolve(db, A, "/d/in.txt")).id == f.id


async def test_trashed_name_does_not_block_new_item_and_restore_renames(db, store):
    old = await put(db, store, A, "root", "a.txt", b"old")
    await svc.trash(db, A, [old.id])
    new = await put(db, store, A, "root", "a.txt", b"new")
    assert new.name == "a.txt"  # 삭제된 이름과 충돌하지 않는다
    (restored,) = await svc.restore(db, A, [old.id])
    assert restored.name == "a (1).txt"  # 복원 때 겹치면 번호를 붙인다


async def test_restore_goes_to_root_when_parent_was_trashed(db, store):
    p = await svc.create_folder(db, A, "root", "p")
    c = await svc.create_folder(db, A, p.id, "c")
    await svc.trash(db, A, [c.id])  # c 를 먼저 지우고
    await svc.trash(db, A, [p.id])  # 부모도 지운다
    (r,) = await svc.restore(db, A, [c.id])
    assert r.parent_id == A  # 부모가 휴지통에 있으므로 루트로


async def test_bulk_trash_skips_children_already_trashed_with_parent(db, store):
    d = await svc.create_folder(db, A, "root", "d")
    f = await put(db, store, A, d.id, "f.txt")
    assert await svc.trash(db, A, [d.id, f.id]) == 1


async def test_purge_removes_objects_rows_and_frees_quota(db, store):
    d = await svc.create_folder(db, A, "root", "d")
    f = await put(db, store, A, d.id, "f.txt", b"12345")
    await svc.trash(db, A, [d.id])
    await svc.purge(db, A, [d.id], store=store)
    assert store.objects == {} and (await svc.usage(db, A))["used_bytes"] == 0
    assert (await db.execute(select(DriveNode).where(DriveNode.id.in_([d.id, f.id])))).first() is None
    with pytest.raises(DriveError):
        await svc.purge(db, A, [d.id], store=store)  # 이미 없다


async def test_purge_requires_trashed_item(db, store):
    f = await put(db, store, A, "root", "f.txt")
    with pytest.raises(DriveError) as e:
        await svc.purge(db, A, [f.id], store=store)
    assert e.value.status == 404 and f.storage_key in store.objects


async def test_empty_trash_and_expiry(db, store):
    a = await put(db, store, A, "root", "a.txt")
    b = await put(db, store, A, "root", "b.txt")
    await svc.trash(db, A, [a.id, b.id])
    assert await svc.purge_expired(db, days=30, store=store) == 0  # 아직 보관 기간 안
    from datetime import timedelta

    for n in (await db.execute(select(DriveNode).where(DriveNode.trashed_at.is_not(None)))).scalars():
        n.trashed_at = svc._now() - timedelta(days=31)
    await db.commit()
    assert await svc.purge_expired(db, days=30, store=store) == 2
    assert store.objects == {}
    assert await svc.purge_expired(db, days=0, store=store) == 0  # 0 이면 자동 삭제 안 함


# ── 소유자 격리 (IDOR) ────────────────────────────────────────
async def test_other_users_cannot_touch_my_nodes(db, store):
    folder = await svc.create_folder(db, A, "root", "private")
    f = await put(db, store, A, folder.id, "secret.txt")
    probes = [
        svc.get_owned(db, B, f.id),
        svc.get_folder(db, B, folder.id),
        svc.rename(db, B, f.id, "x"),
        svc.move(db, B, [f.id], "root"),
        svc.create_folder(db, B, folder.id, "x"),
        put(db, store, B, folder.id, "x.txt"),
    ]
    for coro in probes:
        with pytest.raises(DriveError) as e:
            await coro
        assert e.value.status == 404  # 존재 여부도 알려 주지 않는다
    assert await svc.trash(db, B, [f.id]) == 0  # 남의 항목은 조용히 건너뛰고 지우지 않는다
    assert (await svc.get_owned(db, A, f.id)).name == "secret.txt"
    assert await svc.resolve(db, B, "/private/secret.txt") is None
    # 내 루트에 B 가 접근하려고 'root' 별칭을 써도 B 자신의 루트다
    assert (await svc.get_folder(db, B, "root")).id == B


async def test_move_into_other_users_folder_is_denied(db, store):
    mine = await put(db, store, A, "root", "m.txt")
    theirs = await svc.create_folder(db, B, "root", "theirs")
    with pytest.raises(DriveError) as e:
        await svc.move(db, A, [mine.id], theirs.id)
    assert e.value.status == 404


# ── 경로·대조 ─────────────────────────────────────────────────
async def test_resolve_and_node_path(db, store):
    d = await svc.create_folder(db, A, "root", "보고서")
    f = await put(db, store, A, d.id, "요약.pdf")
    assert (await svc.resolve(db, A, "/보고서/요약.pdf")).id == f.id
    assert (await svc.resolve(db, A, "/보고서/요약.PDF")).id == f.id  # 대소문자 무시
    assert (await svc.resolve(db, A, "/")).id == A
    assert await svc.resolve(db, A, "/없음/x") is None
    assert await svc.node_path(db, f) == "/보고서/요약.pdf"


async def test_reconcile_reports_and_fixes(db, store):
    f = await put(db, store, A, "root", "a.txt", b"abc")
    store.objects[f"drive/{A}/orphan"] = b"zzz"  # 행이 없는 객체
    del_key = (await put(db, store, A, "root", "gone.txt", b"q")).storage_key
    del store.objects[del_key]  # 객체가 없는 행
    rep = await svc.reconcile(db, store=store)
    assert rep["orphan_objects"] == [f"drive/{A}/orphan"] and rep["missing_objects"] == [del_key]
    await db.execute(DriveUsage.__table__.update().values(used_bytes=999))
    await db.commit()
    rep = await svc.reconcile(db, store=store, fix=True)
    assert rep["usage_drift"][0]["actual"] == 4
    assert f"drive/{A}/orphan" not in store.objects
    assert (await svc.usage(db, A))["used_bytes"] == 4


async def test_create_file_survives_session_rollback_during_reserve(db, store, monkeypatch):
    """동시에 첫 업로드를 하면 용량 행 생성이 충돌해 rollback() 이 일어나고 세션 객체가 만료된다 (실제 서버에서 MissingGreenlet 으로 터졌던 경우)."""
    orig = svc._reserve

    async def reserve_then_rollback(d, user_id, nbytes):
        await orig(d, user_id, nbytes)
        await d.rollback()  # 이 세션의 모든 객체가 만료된다

    monkeypatch.setattr(svc, "_reserve", reserve_then_rollback)
    node = await put(db, store, A, "root", "first.txt", b"abc")
    assert node.name == "first.txt" and node.parent_id == A
    assert (await svc.usage(db, A))["used_bytes"] == 3


async def test_empty_trash_when_a_trashed_item_sits_inside_a_later_trashed_folder(db, store):
    """먼저 지운 파일이 들어 있던 폴더를 나중에 지우면 휴지통 묶음이 겹친다 (실제로 '휴지통 비우기'가 404 로 실패했던 경우)."""
    d = await svc.create_folder(db, A, "root", "d")
    f = await put(db, store, A, d.id, "first.txt", b"111")
    keep = await put(db, store, A, d.id, "keep.txt", b"22")
    await svc.trash(db, A, [f.id])
    await svc.trash(db, A, [d.id])
    assert {n.id for n in await svc.list_trash(db, A)} == {f.id, d.id}
    assert await svc.empty_trash(db, A, store=store) >= 1
    assert store.objects == {} and (await svc.usage(db, A))["used_bytes"] == 0
    assert (await db.execute(select(DriveNode).where(DriveNode.id.in_([d.id, f.id, keep.id])))).first() is None


async def test_purge_expired_with_overlapping_trash(db, store):
    from datetime import timedelta

    d = await svc.create_folder(db, A, "root", "d")
    f = await put(db, store, A, d.id, "first.txt")
    await svc.trash(db, A, [f.id])
    await svc.trash(db, A, [d.id])
    for n in (await db.execute(select(DriveNode).where(DriveNode.trashed_at.is_not(None)))).scalars():
        n.trashed_at = svc._now() - timedelta(days=40)
    await db.commit()
    await svc.purge_expired(db, days=30, store=store)  # 예외 없이 끝나야 한다
    assert store.objects == {}

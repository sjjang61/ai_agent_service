"""sandbox(/workspace) ↔ Drive 전송. sandbox 컨테이너에는 MinIO 인증 정보를 주지 않고, 항상 백엔드가 읽어서 Drive 에 쓴다.

저장은 사본이다: 이후 sandbox 파일을 고쳐도 Drive 는 그대로이며, 같은 이름이 있으면 번호를 붙인다(덮어쓰지 않는다).
"""
import hashlib
import os
import posixpath
import shutil
import tarfile
import tempfile
from pathlib import PurePosixPath
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import drive_service as svc
from app.services import drive_storage
from app.services.artifact_service import _ALWAYS_PRUNE
from app.services.drive_service import DriveError

# 저장할 때 건너뛰는 디렉터리 (의존성·캐시·버전관리: 산출물이 아니고 파일 수만 늘린다)
SKIP_DIRS = set(_ALWAYS_PRUNE) | {".venv", "venv", ".next", "dist-info"}
_MB = 1024 * 1024


def _safe_parts(name: str) -> Optional[list]:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts:
        return None
    return [x for x in p.parts if x not in ("", ".")]


def _wanted(parts: list) -> bool:
    return not any(x in SKIP_DIRS for x in parts)


def _scan(tar_path: str) -> tuple[int, int, int]:
    """(저장할 파일 수, 총 바이트, 건너뛴 항목 수). 쓰기 전에 한도를 검사하려고 한 번 훑는다."""
    files = total = skipped = 0
    with tarfile.open(tar_path) as t:
        for m in t:
            parts = _safe_parts(m.name)
            if parts is None or not (m.isfile() or m.isdir()) or not _wanted(parts):
                skipped += 1
                continue
            if m.isfile():
                files += 1
                total += m.size
    return files, total, skipped


async def save_from_sandbox(
    db: AsyncSession, user_id: str, manager, container_id: str, workspace_path: str, parent_id: str,
    name: Optional[str] = None, source: str = "sandbox", source_ref: Optional[dict] = None, store=None,
) -> dict:
    """sandbox 의 파일 또는 폴더 하나를 Drive 폴더(parent_id)로 저장한다. 반환: {node, files, skipped}"""
    parent = await svc.get_folder(db, user_id, parent_id)
    pid = parent.id
    tmpdir = tempfile.mkdtemp(prefix="drive-import-")
    tar_path = os.path.join(tmpdir, "src.tar")
    try:
        try:
            await manager.export_path(container_id, workspace_path, tar_path, settings.DRIVE_IMPORT_MAX_MB * _MB)
        except RuntimeError as e:  # 크기 제한 초과
            raise DriveError(413, f"저장할 수 있는 크기({settings.DRIVE_IMPORT_MAX_MB}MB)를 넘습니다: {e}")
        except Exception as e:  # noqa: BLE001  docker NotFound 등
            raise DriveError(404, f"sandbox 에서 경로를 읽지 못했습니다: {workspace_path} ({type(e).__name__})")
        n_files, total, skipped = _scan(tar_path)
        if n_files == 0:
            raise DriveError(400, "저장할 파일이 없습니다")
        if n_files > settings.DRIVE_IMPORT_MAX_FILES:
            raise DriveError(413, f"한 번에 저장할 수 있는 파일 수({settings.DRIVE_IMPORT_MAX_FILES}개)를 넘습니다 ({n_files}개). 폴더를 나누거나 zip 으로 묶어 저장하세요")
        if total > settings.DRIVE_IMPORT_MAX_MB * _MB:
            raise DriveError(413, f"저장할 수 있는 크기({settings.DRIVE_IMPORT_MAX_MB}MB)를 넘습니다")

        top: Optional[svc.DriveNode] = None
        folders: dict = {}  # tar 안의 폴더 경로(tuple) → Drive 폴더 id
        saved = 0
        with tarfile.open(tar_path) as t:
            for m in t:
                parts = _safe_parts(m.name)
                if parts is None or not (m.isfile() or m.isdir()) or not _wanted(parts):
                    continue
                if m.isdir():
                    if len(parts) == 1:  # 최상위 폴더: 같은 이름이 있으면 번호를 붙여 새로 만든다 (합치지 않는다)
                        taken = await svc._live_names(db, user_id, pid)
                        top = await svc.create_folder(db, user_id, pid, svc.unique_name(svc.normalize_name(name or parts[0]), taken), source=source)
                        folders[tuple(parts)] = top.id
                    else:
                        up = folders.get(tuple(parts[:-1]))
                        if up is not None:
                            folders[tuple(parts)] = (await svc.create_folder(db, user_id, up, parts[-1], source=source)).id
                    continue
                # 파일
                if len(parts) == 1:  # 단일 파일 요청
                    dest = pid
                    fname = svc.normalize_name(name or parts[0])
                else:
                    dest = folders.get(tuple(parts[:-1]))
                    fname = parts[-1]
                    if dest is None:  # tar 에 폴더 항목이 없는 경우: 경로를 만들어 준다
                        dest = pid
                        for i in range(1, len(parts)):
                            key = tuple(parts[:i])
                            if key not in folders:
                                if i == 1:
                                    taken = await svc._live_names(db, user_id, pid)
                                    top = await svc.create_folder(db, user_id, pid, svc.unique_name(svc.normalize_name(name or parts[0]), taken), source=source)
                                    folders[key] = top.id
                                else:
                                    folders[key] = (await svc.create_folder(db, user_id, folders[tuple(parts[:i - 1])], parts[i - 1], source=source)).id
                        dest = folders[tuple(parts[:-1])]
                src = t.extractfile(m)
                with tempfile.SpooledTemporaryFile(max_size=8 * _MB) as buf:
                    h, size = hashlib.sha256(), 0
                    for chunk in iter(lambda: src.read(64 * 1024), b""):
                        h.update(chunk)
                        size += len(chunk)
                        buf.write(chunk)
                    buf.seek(0)
                    node = await svc.create_file(db, user_id, dest, fname, buf, size, h.hexdigest(), source=source,
                                                 source_ref={**(source_ref or {}), "workspace_path": workspace_path}, store=store)
                saved += 1
                if len(parts) == 1:
                    top = node
        return {"node": top, "files": saved, "skipped": skipped}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def load_to_sandbox(
    db: AsyncSession, user_id: str, manager, container_id: str, drive_path: str, dest_path: str, store=None,
) -> dict:
    """Drive 파일 하나를 sandbox 로 복사한다 (dest_path 가 디렉터리 표기(끝이 '/')이면 그 안에 같은 이름으로). 반환: {path, size}"""
    store = store or drive_storage.storage
    node = await svc.resolve(db, user_id, drive_path)
    if node is None:
        raise DriveError(404, f"Drive 에서 경로를 찾을 수 없습니다: {drive_path}")
    if node.type != "file" or not node.storage_key:
        raise DriveError(400, "파일만 불러올 수 있습니다 (폴더는 drive_list 로 내용을 보고 파일별로 불러오세요)")
    limit = settings.DRIVE_LOAD_MAX_MB * _MB
    if int(node.size_bytes or 0) > limit:
        raise DriveError(413, f"{settings.DRIVE_LOAD_MAX_MB}MB 를 넘는 파일은 sandbox 로 불러올 수 없습니다")
    full = dest_path if not dest_path.endswith("/") else posixpath.join(dest_path, node.name)
    data = bytearray()
    async for chunk in store.stream(node.storage_key):
        data.extend(chunk)
        if len(data) > limit:
            raise DriveError(413, f"{settings.DRIVE_LOAD_MAX_MB}MB 를 넘는 파일은 sandbox 로 불러올 수 없습니다")
    await manager.write_file(container_id, full, bytes(data))
    return {"path": full, "size": len(data)}

"""Drive API: 개인 파일 공간(폴더·파일·휴지통·용량). 모든 경로는 로그인한 본인의 항목에만 동작한다."""
import asyncio
import hashlib
import tempfile
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services import drive_sandbox
from app.services import drive_service as svc
from app.services import drive_storage
from app.services.app_policy import RateLimiter
from app.services.drive_service import DriveError, node_dict

router = APIRouter()
_upload_limiter = RateLimiter(settings.DRIVE_UPLOADS_PER_MIN)


def require_drive() -> None:
    if not drive_storage.enabled():
        raise HTTPException(status_code=503, detail="Drive 를 사용할 수 없습니다 (DRIVE_ENABLED 와 MinIO 설정을 확인하세요)")


class FolderCreate(BaseModel):
    parent_id: str = "root"
    name: str


class NodePatch(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class MoveRequest(BaseModel):
    ids: List[str] = Field(min_length=1, max_length=500)
    parent_id: str


class IdsRequest(BaseModel):
    ids: List[str] = Field(min_length=1, max_length=500)


@router.get("/nodes", dependencies=[Depends(require_drive)])
async def list_nodes(
    parent_id: str = "root", sort: str = "name", desc: bool = False, cursor: int = 0, limit: int = 500, folders_only: bool = False,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    """폴더 내용과 경로(breadcrumb). 폴더가 먼저 나온다."""
    folder = await svc.get_folder(db, user.id, parent_id)
    nodes, nxt = await svc.list_children(db, user.id, folder, sort=sort, desc=desc, cursor=cursor, limit=limit, folders_only=folders_only)
    crumbs = await svc.chain(db, folder)
    return {
        "folder": node_dict(folder), "path": "/" + "/".join(n.name for n in crumbs[1:]),
        "breadcrumb": [{"id": n.id, "name": n.name} for n in crumbs], "nodes": [node_dict(n) for n in nodes], "next_cursor": nxt,
    }


@router.post("/folders", dependencies=[Depends(require_drive)])
async def create_folder(data: FolderCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return node_dict(await svc.create_folder(db, user.id, data.parent_id, data.name))


@router.post("/files", dependencies=[Depends(require_drive)])
async def upload_file(
    request: Request, name: str = Query(..., description="저장할 파일 이름"), parent_id: str = Query("root"),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session),
):
    """파일 한 개 업로드. 본문은 파일 바이트 그대로(raw)이며, 받는 도중에 크기를 세어 한도를 넘으면 곧바로 끊는다(Content-Length 를 믿지 않는다)."""
    if not _upload_limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="업로드 요청이 너무 많습니다. 잠시 후 다시 시도하세요", headers={"Retry-After": "30"})
    limit = svc.max_file_bytes()
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise DriveError(413, f"파일은 {settings.DRIVE_MAX_FILE_MB}MB 까지 올릴 수 있습니다")
    tmp = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    try:
        digest, size = hashlib.sha256(), 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise DriveError(413, f"파일은 {settings.DRIVE_MAX_FILE_MB}MB 까지 올릴 수 있습니다")
            digest.update(chunk)
            await run_in_threadpool(tmp.write, chunk)
        tmp.seek(0)
        node = await svc.create_file(db, user.id, parent_id, name, tmp, size, digest.hexdigest())
    finally:
        tmp.close()
    return node_dict(node)


@router.get("/files/{node_id}/download", dependencies=[Depends(require_drive)])
async def download_file(node_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    node = await svc.get_owned(db, user.id, node_id)
    if node.type != "file" or not node.storage_key:
        raise DriveError(400, "파일이 아닙니다")
    headers = {
        # 어떤 파일도 열어 보게 하지 않고 내려받게만 한다 (HTML·SVG 가 같은 출처에서 실행되는 저장형 XSS 방지)
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(node.name)}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Length": str(int(node.size_bytes or 0)),
    }
    return StreamingResponse(drive_storage.storage.stream(node.storage_key), media_type="application/octet-stream", headers=headers)


@router.patch("/nodes/{node_id}", dependencies=[Depends(require_drive)])
async def patch_node(node_id: str, data: NodePatch, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if data.name is None and data.parent_id is None:
        raise DriveError(400, "바꿀 내용이 없습니다")
    node = await svc.get_owned(db, user.id, node_id)
    if data.parent_id is not None:
        await svc.move(db, user.id, [node_id], data.parent_id)
    if data.name is not None:
        node = await svc.rename(db, user.id, node_id, data.name)
    return node_dict(await svc.get_owned(db, user.id, node.id))


@router.post("/nodes/move", dependencies=[Depends(require_drive)])
async def move_nodes(data: MoveRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    moved = await svc.move(db, user.id, data.ids, data.parent_id)
    return {"moved": len(moved)}


@router.post("/nodes/delete", dependencies=[Depends(require_drive)])
async def delete_nodes(data: IdsRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """휴지통으로 옮긴다 (폴더는 하위 전체). 보관 기간이 지나면 영구 삭제된다."""
    return {"trashed": await svc.trash(db, user.id, data.ids)}


@router.get("/usage", dependencies=[Depends(require_drive)])
async def get_usage(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await svc.usage(db, user.id)


@router.get("/resolve", dependencies=[Depends(require_drive)])
async def resolve_path(path: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    node = await svc.resolve(db, user.id, path)
    if node is None:
        raise DriveError(404, f"경로를 찾을 수 없습니다: {path}")
    return {**node_dict(node), "path": await svc.node_path(db, node)}


@router.get("/trash", dependencies=[Depends(require_drive)])
async def list_trash(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"nodes": [node_dict(n) for n in await svc.list_trash(db, user.id)], "retention_days": settings.DRIVE_TRASH_RETENTION_DAYS}


@router.post("/trash/restore", dependencies=[Depends(require_drive)])
async def restore_trash(data: IdsRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"restored": [node_dict(n) for n in await svc.restore(db, user.id, data.ids)]}


@router.post("/trash/purge", dependencies=[Depends(require_drive)])
async def purge_trash(data: IdsRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"purged": await svc.purge(db, user.id, data.ids)}


@router.post("/trash/empty", dependencies=[Depends(require_drive)])
async def empty_trash(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return {"purged": await svc.empty_trash(db, user.id)}


class SandboxImport(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="대화방 id. 없으면 사용자 공용 sandbox")
    paths: List[str] = Field(min_length=1, max_length=50, description="/workspace 기준 파일·폴더 경로")
    parent_id: str = "root"


@router.post("/import/sandbox", dependencies=[Depends(require_drive)])
async def import_from_sandbox(data: SandboxImport, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """sandbox 의 파일·폴더를 Drive 로 저장한다 (사본). 같은 이름은 번호를 붙이고 node_modules·.git 등은 제외한다."""
    from app.services.sandbox_service import SandboxService, resolve_scope, sandbox_manager
    from app.tools.workspace_tools import WORKSPACE, resolve_path

    sb = await SandboxService.get_sandbox(user.id, db, await resolve_scope(data.conversation_id, user.id, db))
    if not sb or sb.status != "running" or not sb.container_id:
        raise DriveError(404, "실행 중인 sandbox 가 없습니다")
    saved, files = [], 0
    for p in data.paths:
        try:
            full = resolve_path(p)
        except ValueError as e:
            raise DriveError(400, str(e))
        if full == WORKSPACE:
            raise DriveError(400, "작업공간 전체는 저장할 수 없습니다. 파일이나 폴더를 지정하세요")
        r = await drive_sandbox.save_from_sandbox(
            db, user.id, sandbox_manager, sb.container_id, full, data.parent_id, source="sandbox",
            source_ref={"conversation_id": data.conversation_id},
        )
        saved.append(node_dict(r["node"]))
        files += r["files"]
    return {"saved": saved, "files": files}


class AttachRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="대화방 id. 없으면 사용자 공용 sandbox")


@router.post("/files/{node_id}/attach", dependencies=[Depends(require_drive)])
async def attach_to_chat(node_id: str, data: AttachRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Drive 파일을 채팅 첨부로 쓴다: sandbox 의 /workspace/uploads/ 로 복사하고 첨부 정보({name, path, size})를 돌려준다."""
    from app.services.attachment_service import UPLOAD_DIR
    from app.services.sandbox_service import SandboxService, resolve_scope, sandbox_manager

    node = await svc.get_owned(db, user.id, node_id)
    if node.type != "file":
        raise DriveError(400, "파일만 첨부할 수 있습니다")
    if int(node.size_bytes or 0) > settings.UPLOAD_MAX_MB * 1024 * 1024:
        raise DriveError(413, f"첨부 파일은 {settings.UPLOAD_MAX_MB}MB 까지 가능합니다")
    sb = await SandboxService.get_or_create_sandbox(user.id, db, await resolve_scope(data.conversation_id, user.id, db))
    _, listing, _ = await sandbox_manager.exec_command(sb.container_id, f"ls -1A {UPLOAD_DIR} 2>/dev/null", timeout=15)
    final = svc.unique_name(node.name, {n.casefold() for n in listing.splitlines() if n})  # 이미 올린 첨부와 이름이 겹치지 않게
    r = await drive_sandbox.load_to_sandbox(db, user.id, sandbox_manager, sb.container_id, await svc.node_path(db, node), f"{UPLOAD_DIR}/{final}")
    return {"name": final, "path": r["path"], "size": r["size"]}

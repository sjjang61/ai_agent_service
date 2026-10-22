import posixpath
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app.services import artifact_service, publish_service
from app.services.attachment_service import MAX_ATTACHMENTS, UPLOAD_DIR
from app.tools.workspace_tools import WORKSPACE, resolve_path
from app.services.sandbox_service import SandboxService, sandbox_backup, sandbox_manager

router = APIRouter()


@router.get("/status")
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb:
        return {"status": "not_created", "container_id": None}
    return {
        "status": sb.status,
        "container_id": sb.container_id,
        "session_id": sb.id,
        "last_used_at": sb.last_used_at,
    }


@router.post("/start")
async def start_sandbox(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sb = await SandboxService.get_or_create_sandbox(current_user.id, db)
    return {
        "status": sb.status,
        "container_id": sb.container_id,
        "session_id": sb.id,
        "restored": getattr(sb, "restored", False),  # MinIO 백업에서 환경을 복구했는지
    }


@router.post("/stop")
async def stop_sandbox(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb or not sb.container_id:
        raise HTTPException(status_code=404, detail="No active sandbox")
    try:
        # 백업이 활성화되어 있으면 /workspace 를 MinIO 에 저장한 뒤 종료한다
        await SandboxService.suspend(sb.id, db)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"백업에 실패해 sandbox 를 유지합니다: {e}"
        )
    return {"status": "stopped", "backed_up": sandbox_backup.enabled}


@router.get("/files")
async def list_files(
    path: str = "/workspace",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb or sb.status != "running":
        raise HTTPException(status_code=404, detail="No running sandbox")
    _, stdout, _ = await sandbox_manager.exec_command(sb.container_id, f"ls -la {path}")
    return {"path": path, "listing": stdout}


@router.get("/files/{file_path:path}")
async def get_file(
    file_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb or sb.status != "running":
        raise HTTPException(status_code=404, detail="No running sandbox")
    await SandboxService.touch(sb, db)  # 사용자가 파일을 열람 = 사용 이력
    _, stdout, stderr = await sandbox_manager.exec_command(
        sb.container_id, f"cat /workspace/{file_path}"
    )
    if stderr:
        raise HTTPException(status_code=404, detail=f"File error: {stderr}")
    return {"path": file_path, "content": stdout}


@router.get("/workspace-tree")
async def workspace_tree(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """워크스페이스 내 파일 목록을 JSON으로 반환."""
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb or sb.status != "running":
        return {"files": []}
    _, stdout, _ = await sandbox_manager.exec_command(
        sb.container_id,
        "find /workspace -maxdepth 5 -type f 2>/dev/null | sed 's|/workspace/||' | sort",
    )
    files = [line.strip() for line in stdout.splitlines() if line.strip()]
    return {"files": files}


# ── 산출물(artifacts) ─────────────────────────────────────────────────────────
async def _running_sandbox(user_id: str, db: AsyncSession):
    sb = await SandboxService.get_sandbox(user_id, db)
    if not sb or sb.status != "running" or not sb.container_id:
        raise HTTPException(status_code=404, detail="실행 중인 sandbox 가 없습니다")
    return sb


def _artifact_path(rel: str) -> str:
    try:
        full = resolve_path(rel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if full == WORKSPACE:
        raise HTTPException(status_code=400, detail="파일 경로를 지정하세요")
    return full


async def _read_artifact(sb, full: str, max_bytes: int) -> tuple[bytes, int]:
    try:
        return await sandbox_manager.read_file(sb.container_id, full, max_bytes)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    except IsADirectoryError:
        raise HTTPException(status_code=400, detail="디렉터리입니다")
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.get("/artifacts")
async def list_artifacts(
    hidden: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """sandbox 작업공간의 산출물 목록 (크기·수정시각·종류 포함, 최근 수정순)."""
    sb = await SandboxService.get_sandbox(current_user.id, db)
    if not sb or sb.status != "running" or not sb.container_id:
        # 유휴 종료된 sandbox 는 시작하면 MinIO 백업에서 복구된다
        restorable = False
        if sb and sandbox_backup.enabled:
            try:
                restorable = await sandbox_backup.exists(sb.id)
            except Exception:
                restorable = False
        return {"status": sb.status if sb else "not_created", "files": [], "truncated": False, "restorable": restorable}
    _, out, _ = await sandbox_manager.exec_command(sb.container_id, artifact_service.list_command(hidden), timeout=30)
    files, truncated = artifact_service.parse_listing(out)
    return {"status": "running", "files": files, "truncated": truncated, "restorable": False}


@router.get("/artifacts/preview")
async def preview_artifact(
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """텍스트 파일 미리보기 (이미지/바이너리는 kind 만 알려준다)."""
    sb = await _running_sandbox(current_user.id, db)
    full = _artifact_path(path)
    await SandboxService.touch(sb, db)
    kind, _ = artifact_service.classify(full)
    max_bytes = settings.ARTIFACT_PREVIEW_MAX_KB * 1024
    if kind == "image":
        return {"path": path, "kind": "image"}
    try:
        # 한도보다 조금 더 읽어 잘렸는지 판단한다 (큰 파일은 413 이므로 크기만 알려준다)
        data, _ = await sandbox_manager.read_file(sb.container_id, full, 5 * 1024 * 1024)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
    except IsADirectoryError:
        raise HTTPException(status_code=400, detail="디렉터리입니다")
    except ValueError:
        return {"path": path, "kind": "too_large"}
    if b"\x00" in data[:8192]:
        return {"path": path, "kind": "binary", "size": len(data)}
    truncated = len(data) > max_bytes
    return {
        "path": path, "kind": "text", "size": len(data), "truncated": truncated,
        "content": data[:max_bytes].decode("utf-8", errors="replace"),
    }


@router.get("/artifacts/raw")
async def raw_artifact(
    path: str,
    download: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """파일 원본(바이너리 안전). download=false 는 이미지 미리보기용 (이미지 형식만 inline)."""
    sb = await _running_sandbox(current_user.id, db)
    full = _artifact_path(path)
    await SandboxService.touch(sb, db)
    name = full.rsplit("/", 1)[-1]
    kind, mime = artifact_service.classify(name)
    max_mb = settings.ARTIFACT_MAX_DOWNLOAD_MB if download else 10
    data, _ = await _read_artifact(sb, full, max_mb * 1024 * 1024)
    headers = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"}
    if download or kind != "image":
        headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
        return Response(content=data, media_type="application/octet-stream", headers=headers)
    return Response(content=data, media_type=mime, headers=headers)


class PublishArtifactRequest(BaseModel):
    path: str
    expires_hours: Optional[int] = None


@router.post("/artifacts/publish")
async def publish_artifact(
    data: PublishArtifactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """파일을 공개 다운로드 링크로 발행한다 (링크를 아는 사람은 누구나 만료 전까지 내려받을 수 있음)."""
    sb = await _running_sandbox(current_user.id, db)
    full = _artifact_path(data.path)
    content, _ = await _read_artifact(sb, full, settings.PUBLISH_MAX_MB * 1024 * 1024)
    try:
        return publish_service.publish(current_user.id, full.rsplit("/", 1)[-1], content, data.expires_hours)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))


# ── 첨부 파일 업로드 ──────────────────────────────────────────────────────────
def _unique_name(name: str, existing: set[str]) -> str:
    if name not in existing:
        return name
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    for i in range(1, 1000):
        cand = f"{stem} ({i}){'.' + ext if ext else ''}"
        if cand not in existing:
            return cand
    raise HTTPException(status_code=409, detail="같은 이름의 파일이 너무 많습니다")


@router.post("/uploads")
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """채팅 첨부 파일을 사용자의 sandbox(/workspace/uploads/)에 올린다. 같은 이름은 `이름 (1).ext` 로 저장한다."""
    if not files or len(files) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=400, detail=f"한 번에 1~{MAX_ATTACHMENTS}개의 파일을 올릴 수 있습니다")
    limit = settings.UPLOAD_MAX_MB * 1024 * 1024

    # 메모리를 아끼기 위해 먼저 크기를 확인한다 (limit 초과분은 읽지 않는다)
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"'{f.filename}' 이(가) 너무 큽니다 (최대 {settings.UPLOAD_MAX_MB}MB)")
        payloads.append((publish_service.safe_filename(f.filename or "file"), data))

    try:
        sb = await SandboxService.get_or_create_sandbox(current_user.id, db)
        _, listing, _ = await sandbox_manager.exec_command(
            sb.container_id, f"ls -1A {UPLOAD_DIR} 2>/dev/null", timeout=15
        )
        existing = {n for n in listing.splitlines() if n}
        saved = []
        for name, data in payloads:
            final = _unique_name(name, existing)
            existing.add(final)
            await sandbox_manager.write_file(sb.container_id, posixpath.join(UPLOAD_DIR, final), data)
            saved.append({"name": final, "path": posixpath.join(UPLOAD_DIR, final), "size": len(data)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sandbox 에 업로드하지 못했습니다: {e}")
    return {"files": saved}


def _safe_relative_path(raw: str) -> list[str]:
    """브라우저가 보낸 폴더 안 상대 경로를 검증해 안전한 경로 조각으로 돌려준다. 위험한 경로는 400."""
    parts = [p for p in raw.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or len(parts) > 9 or any(p == ".." for p in parts):
        raise HTTPException(status_code=400, detail=f"허용되지 않는 폴더 경로입니다: {raw[:80]}")
    return [publish_service.safe_filename(p) for p in parts]


@router.post("/uploads/folder")
async def upload_folder(
    files: List[UploadFile] = File(...),
    paths: List[str] = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """폴더 하나를 사용자의 sandbox(/workspace/uploads/<폴더>/)에 구조 그대로 올린다.

    paths 는 files 와 같은 순서의 상대 경로(webkitRelativePath: '폴더/하위/파일'). 같은 이름의 폴더가 있으면 `이름 (1)` 로 저장한다.
    """
    import tempfile
    from pathlib import Path

    if not files or len(files) != len(paths):
        raise HTTPException(status_code=400, detail="files 와 paths 의 개수가 맞지 않습니다")
    if len(files) > settings.UPLOAD_FOLDER_MAX_FILES:
        raise HTTPException(status_code=400, detail=f"폴더는 파일 {settings.UPLOAD_FOLDER_MAX_FILES}개까지 올릴 수 있습니다")
    per_file = settings.UPLOAD_MAX_MB * 1024 * 1024
    budget = settings.UPLOAD_FOLDER_MAX_MB * 1024 * 1024

    rels = [_safe_relative_path(p) for p in paths]
    root = rels[0][0]
    if any(r[0] != root for r in rels):
        raise HTTPException(status_code=400, detail="하나의 폴더만 올릴 수 있습니다")
    if any(len(r) < 2 for r in rels):
        raise HTTPException(status_code=400, detail="폴더 안의 파일 경로가 필요합니다")

    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / root
        for f, rel in zip(files, rels):
            data = await f.read(per_file + 1)
            if len(data) > per_file:
                raise HTTPException(status_code=413, detail=f"'{'/'.join(rel)}' 이(가) 너무 큽니다 (파일당 최대 {settings.UPLOAD_MAX_MB}MB)")
            total += len(data)
            if total > budget:
                raise HTTPException(status_code=413, detail=f"폴더가 너무 큽니다 (최대 {settings.UPLOAD_FOLDER_MAX_MB}MB)")
            target = base.joinpath(*rel[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        try:
            sb = await SandboxService.get_or_create_sandbox(current_user.id, db)
            _, listing, _ = await sandbox_manager.exec_command(sb.container_id, f"ls -1A {UPLOAD_DIR} 2>/dev/null", timeout=15)
            final = _unique_name(root, {n for n in listing.splitlines() if n})
            await sandbox_manager.put_directory(sb.container_id, base, UPLOAD_DIR, final)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sandbox 에 업로드하지 못했습니다: {e}")
    return {"files": [{"name": final, "path": posixpath.join(UPLOAD_DIR, final), "size": total, "kind": "folder", "file_count": len(files)}]}

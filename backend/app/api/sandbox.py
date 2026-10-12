from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
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

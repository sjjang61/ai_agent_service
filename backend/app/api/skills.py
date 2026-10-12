from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.skill import Skill
from app.models.user import User
from app.schemas.skill import SkillInstallRequest, SkillInstallResponse, SkillResponse, SkillSyncResponse
from app.services.skill_service import SkillService

router = APIRouter()


def _to_response(s: Skill) -> SkillResponse:
    return SkillResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        source_url=s.source_url,
        is_active=s.is_active,
        created_at=s.created_at,
    )


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    return [_to_response(s) for s in await SkillService.list_skills(current_user.id, db)]


@router.post("/install", response_model=SkillInstallResponse)
async def install_skill(
    data: SkillInstallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    skills, sandbox_error = await SkillService.install(current_user.id, data.url, db)
    return SkillInstallResponse(
        installed=[_to_response(s) for s in skills],
        sandbox_synced=sandbox_error is None,
        sandbox_error=sandbox_error,
    )


@router.post("/sync", response_model=SkillSyncResponse)
async def sync_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """설치된 skill 전체를 sandbox 로 다시 복사 (sandbox 가 재생성된 경우 등)."""
    skills = [s for s in await SkillService.list_skills(current_user.id, db) if s.is_active]
    err = await SkillService.sync_to_sandbox(current_user.id, skills, db)
    return SkillSyncResponse(synced=0 if err else len(skills), sandbox_error=err)


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await SkillService.delete(skill_id, current_user.id, db)
    return {"status": "deleted"}

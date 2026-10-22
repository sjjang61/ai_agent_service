from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.plugin import Plugin
from app.models.skill import Skill
from app.models.user import User
from app.schemas.skill import (
    ActiveRequest,
    PluginInstallResponse,
    PluginResponse,
    SkillCreateRequest,
    SkillInstallRequest,
    SkillInstallResponse,
    SkillResponse,
    SkillSyncResponse,
)
from app.services.skill_service import SkillService

router = APIRouter()


def _to_response(s: Skill, plugins: dict | None = None) -> SkillResponse:
    owner = (plugins or {}).get(s.name)
    return SkillResponse(
        plugin_id=owner.id if owner else None,
        plugin_name=owner.name if owner else None,
        id=s.id,
        name=s.name,
        description=s.description,
        source_url=s.source_url,
        is_active=s.is_active,
        created_at=s.created_at,
    )


def _plugin_response(p: Plugin) -> PluginResponse:
    return PluginResponse(
        id=p.id, name=p.name, description=p.description, version=p.version,
        source_url=p.source_url, is_active=p.is_active,
        skill_names=list(p.skill_names or []), created_at=p.created_at,
    )


def _owner_map(plugins: List[Plugin]) -> dict:
    return {n: p for p in plugins for n in (p.skill_names or [])}


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    owners = _owner_map(await SkillService.list_plugins(current_user.id, db))
    return [_to_response(s, owners) for s in await SkillService.list_skills(current_user.id, db)]


@router.post("/custom", response_model=SkillInstallResponse)
async def create_custom_skill(
    data: SkillCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """직접 작성한 SKILL.md 로 skill 추가"""
    skill, sandbox_error = await SkillService.create_custom(
        current_user.id, data.name, data.description, data.content, db
    )
    return SkillInstallResponse(
        installed=[_to_response(skill)], sandbox_synced=sandbox_error is None, sandbox_error=sandbox_error
    )


@router.get("/plugins", response_model=List[PluginResponse])
async def list_plugins(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    return [_plugin_response(p) for p in await SkillService.list_plugins(current_user.id, db)]


@router.post("/plugins/install", response_model=PluginInstallResponse)
async def install_plugin(
    data: SkillInstallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """GitHub URL 의 플러그인(.claude-plugin/plugin.json 또는 marketplace.json)을 설치"""
    plugins, skills, sandbox_error = await SkillService.install_plugin(current_user.id, data.url, db)
    owners = _owner_map(plugins)
    return PluginInstallResponse(
        installed=[_plugin_response(p) for p in plugins],
        skills=[_to_response(s, owners) for s in skills],
        sandbox_synced=sandbox_error is None,
        sandbox_error=sandbox_error,
    )


@router.post("/plugins/{plugin_id}/active", response_model=PluginResponse)
async def set_plugin_active(
    plugin_id: str,
    data: ActiveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    return _plugin_response(await SkillService.set_plugin_active(plugin_id, current_user.id, data.is_active, db))


@router.delete("/plugins/{plugin_id}")
async def delete_plugin(
    plugin_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await SkillService.delete_plugin(plugin_id, current_user.id, db)
    return {"status": "deleted"}


@router.post("/{skill_id}/active", response_model=SkillResponse)
async def set_skill_active(
    skill_id: str,
    data: ActiveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    skill = await SkillService.set_active(skill_id, current_user.id, data.is_active, db)
    owners = _owner_map(await SkillService.list_plugins(current_user.id, db))
    return _to_response(skill, owners)


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

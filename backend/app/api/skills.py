from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
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
from app.config import settings
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


@router.post("/plugins/upload", response_model=PluginInstallResponse)
async def upload_plugin_zip(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """zip 파일로 플러그인 설치 (.claude-plugin/plugin.json 또는 marketplace.json 포함)"""
    name = file.filename or "plugin.zip"
    if not name.lower().endswith(".zip"):
        raise HTTPException(400, ".zip 파일만 올릴 수 있습니다")
    limit = settings.SKILL_MAX_DOWNLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"파일이 너무 큽니다 (최대 {settings.SKILL_MAX_DOWNLOAD_MB}MB)")
    plugins, skills, sandbox_error = await SkillService.install_plugin_zip(current_user.id, name, data, db)
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


class SkillFileInfo(BaseModel):
    path: str
    size: int


class SkillDetail(SkillResponse):
    files: List[SkillFileInfo] = []
    truncated: bool = False


class SkillFileContent(BaseModel):
    path: str
    size: int
    binary: bool = False
    truncated: bool = False
    content: str = ""


@router.get("/{skill_id}/detail", response_model=SkillDetail)
async def get_skill_detail(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """skill 상세: 메타 정보와 폴더의 파일 목록"""
    skill = await SkillService.get_skill(skill_id, current_user.id, db)
    owners = _owner_map(await SkillService.list_plugins(current_user.id, db))
    files, truncated = SkillService.list_files(skill)
    return SkillDetail(**_to_response(skill, owners).model_dump(), files=files, truncated=truncated)


@router.get("/{skill_id}/file", response_model=SkillFileContent)
async def get_skill_file(
    skill_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """skill 폴더 안의 파일 내용 (텍스트, 최대 200KB)"""
    skill = await SkillService.get_skill(skill_id, current_user.id, db)
    return SkillService.read_file(skill, path)


class TranslateRequest(BaseModel):
    path: str


class TranslateResponse(BaseModel):
    path: str
    content: str
    truncated: bool = False


@router.post("/{skill_id}/translate", response_model=TranslateResponse)
async def translate_skill_file(
    skill_id: str,
    data: TranslateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """skill 의 텍스트 파일(SKILL.md 등)을 한국어로 번역한다 (결과는 서버 메모리에 캐시)."""
    from pathlib import Path

    from app.services.skill_translate import translate_to_korean

    skill = await SkillService.get_skill(skill_id, current_user.id, db)
    f = SkillService.read_file(skill, data.path)
    if f["binary"]:
        raise HTTPException(400, "바이너리 파일은 번역할 수 없습니다")
    st = (Path(skill.install_path) / data.path).stat()
    try:
        r = await translate_to_korean(f["content"], (skill.id, data.path, int(st.st_mtime), st.st_size))
    except Exception as e:  # LLM 호출 실패·시간 초과
        raise HTTPException(502, f"번역하지 못했습니다: {type(e).__name__}") from e
    return TranslateResponse(path=data.path, content=r["content"], truncated=r["truncated"] or f["truncated"])


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


@router.post("/upload", response_model=SkillInstallResponse)
async def upload_skill_zip(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """zip 파일로 skill 설치 (SKILL.md 가 있는 폴더를 압축한 파일. 폴더 여러 개도 가능)"""
    name = file.filename or "skill.zip"
    if not name.lower().endswith(".zip"):
        raise HTTPException(400, ".zip 파일만 올릴 수 있습니다")
    limit = settings.SKILL_MAX_DOWNLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"파일이 너무 큽니다 (최대 {settings.SKILL_MAX_DOWNLOAD_MB}MB)")
    skills, sandbox_error = await SkillService.install_zip(current_user.id, name, data, db)
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

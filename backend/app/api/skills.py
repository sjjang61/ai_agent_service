from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
    SandboxInstallRequest,
    SandboxInstallResponse,
    SandboxSkill,
    SandboxSkillList,
    SkillSyncResponse,
    SkillTypeRequest,
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
        skill_type=s.skill_type or "builtin",
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
        current_user.id, data.name, data.description, data.content, db, data.skill_type
    )
    return SkillInstallResponse(
        installed=[_to_response(skill)], sandbox_synced=sandbox_error is None, sandbox_error=sandbox_error
    )


@router.get("/sandbox", response_model=SandboxSkillList)
async def list_sandbox_skills(
    conversation_id: Optional[str] = None,
    skill_type: str = "custom",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """대화 입력창의 스킬 선택용: 활성 스킬(기본 custom)과 각 스킬이 현재 sandbox 에 설치되어 있는지.
    sandbox 가 꺼져 있으면 시작하지 않고 모두 미설치로 돌려준다 (켤 때 시작·복구된다)."""
    from app.services.sandbox_service import resolve_scope

    skills = [
        s for s in await SkillService.list_skills(current_user.id, db)
        if s.is_active and (skill_type == "all" or (s.skill_type or "builtin") == skill_type)
    ]
    sb = await SkillService.running_sandbox(current_user.id, db, await resolve_scope(conversation_id, current_user.id, db))
    present = await SkillService.installed_in_sandbox(sb.container_id) if sb else set()
    return SandboxSkillList(
        sandbox_running=sb is not None,
        skills=[
            SandboxSkill(id=s.id, name=s.name, description=s.description, skill_type=s.skill_type or "builtin", installed=s.name in present)
            for s in sorted(skills, key=lambda x: x.name)
        ],
    )


@router.post("/{skill_id}/sandbox", response_model=SandboxInstallResponse)
async def set_skill_in_sandbox(
    skill_id: str,
    data: SandboxInstallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """스킬을 현재 sandbox 에 동적으로 설치(installed=true)하거나 제거(false)한다.
    설치할 때 sandbox 가 꺼져 있으면 시작(백업 복구)한다. 제거는 /workspace/skills/<이름> 폴더만 지운다."""
    from app.services.sandbox_service import SandboxService, resolve_scope, sandbox_manager
    from app.services.skill_service import SANDBOX_SKILLS_DIR

    skill = await SkillService.get_skill(skill_id, current_user.id, db)
    scope = await resolve_scope(data.conversation_id, current_user.id, db)
    if data.installed:
        sb = await SandboxService.get_or_create_sandbox(current_user.id, db, scope)
        await SkillService.ensure_in_sandbox(sb.container_id, [skill])
        if skill.name not in await SkillService.installed_in_sandbox(sb.container_id):
            raise HTTPException(500, "스킬 파일을 sandbox 에 설치하지 못했습니다 (스킬을 다시 설치해 보세요)")
        return SandboxInstallResponse(installed=True)
    sb = await SkillService.running_sandbox(current_user.id, db, scope)
    if sb:
        await sandbox_manager.remove_path(sb.container_id, f"{SANDBOX_SKILLS_DIR}/{skill.name}")
    return SandboxInstallResponse(installed=False, sandbox_running=sb is not None)


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
    refresh: bool = False  # True 면 저장된 번역을 무시하고 다시 번역


class TranslateResponse(BaseModel):
    path: str
    content: str
    truncated: bool = False
    cached: bool = False  # 저장된 번역 기록을 그대로 불러왔는지 (AI 호출 없음)
    translated_at: Optional[datetime] = None


@router.post("/{skill_id}/translate", response_model=TranslateResponse)
async def translate_skill_file(
    skill_id: str,
    data: TranslateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """skill 의 텍스트 파일(SKILL.md 등)을 한국어로 번역한다.
    원문이 같은 번역 기록이 있으면 AI 를 부르지 않고 그대로 돌려주고, 내용이 바뀌었거나 refresh 면 새로 번역해 저장한다."""
    from app.services.skill_translate import get_saved, save_translation, translate_to_korean

    skill = await SkillService.get_skill(skill_id, current_user.id, db)
    f = SkillService.read_file(skill, data.path)
    if f["binary"]:
        raise HTTPException(400, "바이너리 파일은 번역할 수 없습니다")
    saved = None if data.refresh else await get_saved(db, current_user.id, f["content"])
    if saved:
        return TranslateResponse(
            path=data.path, content=saved.translated, truncated=saved.truncated or f["truncated"], cached=True, translated_at=saved.created_at
        )
    try:
        r = await translate_to_korean(f["content"])
    except Exception as e:  # LLM 호출 실패·시간 초과
        raise HTTPException(502, f"번역하지 못했습니다: {type(e).__name__}") from e
    row = await save_translation(db, current_user.id, f["content"], r["content"], r["truncated"])
    return TranslateResponse(
        path=data.path, content=r["content"], truncated=r["truncated"] or f["truncated"], cached=False, translated_at=row.created_at
    )


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


@router.post("/{skill_id}/type", response_model=SkillInstallResponse)
async def set_skill_type(
    skill_id: str,
    data: SkillTypeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """스킬 타입 변경. builtin: sandbox 가 만들어질 때 자동 설치 / custom: 자동 설치하지 않고 load_skill 때 필요한 sandbox 에 설치."""
    skill, err = await SkillService.set_type(skill_id, current_user.id, data.skill_type, db)
    owners = _owner_map(await SkillService.list_plugins(current_user.id, db))
    return SkillInstallResponse(installed=[_to_response(skill, owners)], sandbox_synced=err is None, sandbox_error=err)


@router.post("/install", response_model=SkillInstallResponse)
async def install_skill(
    data: SkillInstallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    skills, sandbox_error = await SkillService.install(current_user.id, data.url, db, data.skill_type)
    return SkillInstallResponse(
        installed=[_to_response(s) for s in skills],
        sandbox_synced=sandbox_error is None,
        sandbox_error=sandbox_error,
    )


@router.post("/upload", response_model=SkillInstallResponse)
async def upload_skill_zip(
    file: UploadFile = File(...),
    skill_type: Optional[str] = Form(None),
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
    if skill_type not in (None, "", "builtin", "custom"):
        raise HTTPException(400, "타입은 builtin 또는 custom 이어야 합니다")
    skills, sandbox_error = await SkillService.install_zip(current_user.id, name, data, db, skill_type or None)
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
    skills = [s for s in await SkillService.list_skills(current_user.id, db) if s.is_active and s.skill_type != "custom"]
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

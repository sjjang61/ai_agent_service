from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class SkillInstallRequest(BaseModel):
    url: str
    skill_type: Optional[Literal["builtin", "custom"]] = None  # 스킬 설치에만 쓴다 (플러그인은 builtin)


class SkillTypeRequest(BaseModel):
    skill_type: Literal["builtin", "custom"]


class SkillResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source_url: str
    is_active: bool
    created_at: datetime
    plugin_id: Optional[str] = None
    plugin_name: Optional[str] = None
    skill_type: str = "builtin"  # builtin: sandbox 생성 시 자동 설치 / custom: 필요할 때 설치


class SkillCreateRequest(BaseModel):
    """직접 작성한 skill (SKILL.md 본문)"""
    name: str
    description: str
    content: str
    skill_type: Optional[Literal["builtin", "custom"]] = None


class ActiveRequest(BaseModel):
    is_active: bool


class PluginResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    source_url: str
    is_active: bool
    skill_names: List[str] = []
    created_at: datetime


class PluginInstallResponse(BaseModel):
    installed: List[PluginResponse]
    skills: List[SkillResponse]
    sandbox_synced: bool = True
    sandbox_error: Optional[str] = None


class SkillInstallResponse(BaseModel):
    installed: List[SkillResponse]
    sandbox_synced: bool = True
    sandbox_error: Optional[str] = None


class SkillSyncResponse(BaseModel):
    synced: int
    sandbox_error: Optional[str] = None

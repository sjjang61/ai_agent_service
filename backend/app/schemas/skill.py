from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class SkillInstallRequest(BaseModel):
    url: str
    skill_type: Optional[Literal["builtin", "custom"]] = None  # 스킬 설치에만 쓴다. 비우면 custom


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
    category: str = "etc"  # description 으로 자동 분류한 카테고리 id
    category_locked: bool = False  # 사용자가 직접 고른 카테고리


class CategoryRequest(BaseModel):
    category: str  # 카테고리 id 또는 'auto'(자동 분류로 되돌림)


class CategoryInfo(BaseModel):
    id: str
    label: str


class RecategorizeResponse(BaseModel):
    changed: int
    total: int


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


class SandboxSkill(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    skill_type: str = "custom"
    installed: bool = False  # 현재 sandbox 에 설치(로드)되어 있는지


class SandboxSkillList(BaseModel):
    sandbox_running: bool
    skills: List[SandboxSkill] = []


class SandboxInstallRequest(BaseModel):
    installed: bool  # True: 현재 sandbox 에 설치, False: 현재 sandbox 에서 제거
    conversation_id: Optional[str] = None


class SandboxInstallResponse(BaseModel):
    installed: bool
    sandbox_running: bool = True

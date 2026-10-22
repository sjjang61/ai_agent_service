from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SkillInstallRequest(BaseModel):
    url: str


class SkillResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    source_url: str
    is_active: bool
    created_at: datetime
    plugin_id: Optional[str] = None
    plugin_name: Optional[str] = None


class SkillCreateRequest(BaseModel):
    """직접 작성한 skill (SKILL.md 본문)"""
    name: str
    description: str
    content: str


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

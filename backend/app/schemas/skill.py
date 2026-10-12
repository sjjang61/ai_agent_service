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


class SkillInstallResponse(BaseModel):
    installed: List[SkillResponse]
    sandbox_synced: bool = True
    sandbox_error: Optional[str] = None


class SkillSyncResponse(BaseModel):
    synced: int
    sandbox_error: Optional[str] = None

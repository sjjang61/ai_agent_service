from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MCPServerCreate(BaseModel):
    name: str
    display_name: str
    transport: str = "stdio"
    command: Optional[str] = None
    args: List[str] = []
    url: Optional[str] = None
    env: Dict[str, str] = {}


class MCPServerUpdate(BaseModel):
    display_name: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class MCPServerResponse(BaseModel):
    id: str
    name: str
    display_name: str
    transport: str
    command: Optional[str]
    args: List[str]
    url: Optional[str]
    is_active: bool
    created_at: datetime


class MCPToolResponse(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = {}

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    llm_provider: Optional[str] = None  # 미지정 시 settings.LLM_TYPE
    model_name: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    llm_provider: str
    model_name: str
    created_at: datetime
    updated_at: datetime


class Attachment(BaseModel):
    name: str = ""
    path: str
    size: int = 0


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    agent_steps: List[Any] = []
    tool_calls: List[Any] = []
    attachments: List[Attachment] = []
    created_at: datetime


class SendMessageRequest(BaseModel):
    content: str = ""
    attachments: List[Attachment] = []
    llm_provider: Optional[str] = None
    model: Optional[str] = None

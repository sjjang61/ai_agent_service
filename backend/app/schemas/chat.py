from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    llm_provider: Optional[str] = None  # 미지정 시 settings.LLM_TYPE
    model_name: Optional[str] = None
    agent_id: Optional[str] = None  # 커스텀 에이전트로 시작 (발행된 버전에 고정된다)
    is_test: bool = False  # 에이전트 빌더의 미리보기 대화 (목록에 나타나지 않고 초안으로 실행된다)


class ConversationResponse(BaseModel):
    id: str
    title: str
    llm_provider: str
    model_name: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_icon: Optional[str] = None
    agent_version: Optional[int] = None
    is_test: bool = False
    created_at: datetime
    updated_at: datetime


class Attachment(BaseModel):
    name: str = ""
    path: str
    size: int = 0
    kind: Literal["file", "folder"] = "file"  # folder: path 가 업로드한 폴더(디렉터리)
    file_count: int = 0  # folder 일 때 파일 수


class Reference(BaseModel):
    """질문에 참고 자료로 붙이는 스페이스 페이지나 이전 대화"""
    type: Literal["page", "conversation"]
    id: str
    title: str = ""


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    agent_steps: List[Any] = []
    tool_calls: List[Any] = []
    attachments: List[Attachment] = []
    references: List[Reference] = []
    memory_saved: List[Any] = []  # 이 응답에서 자동 저장된 메모리 [{key, value, scope, action}]
    created_at: datetime


class SendMessageRequest(BaseModel):
    # 빌더 미리보기(is_test 대화)에서 저장하지 않은 편집 내용으로 실행할 때만 사용한다
    agent_config: Optional[dict] = None
    content: str = ""
    attachments: List[Attachment] = []
    references: List[Reference] = []  # 참고 자료로 붙일 스페이스 페이지·이전 대화 (최대 5개)
    llm_provider: Optional[str] = None
    model: Optional[str] = None
    timezone: Optional[str] = None  # 브라우저 시간대(IANA). 예약 도구의 기본값과 '현재 시각' 안내에 쓴다

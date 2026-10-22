"""커스텀 에이전트: 설정(AgentConfig)과 API 스키마.

AgentConfig 는 초안(agents.draft_config)과 발행 버전(agent_versions.config)에 JSON 으로 저장되며,
실행 시 AgentOrchestrator 가 이를 해석해 프롬프트·도구·스킬·MCP·팀 구성에 반영한다.
"""
import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")

# 선택 가능한 도구 이름 (스킬/MCP 도구는 각각 skills/mcp 섹션이 제어한다)
SELECTABLE_TOOLS = [
    "web_search", "web_crawler", "read_file", "write_file", "edit_file", "grep_file", "delete_file",
    "read_image", "code_executor", "exec_command", "download_file", "publish_file", "create_widget",
    "memory_tool", "search_documents", "todo", "narrate", "form_ask_user", "cli_browser_agent",
    "manage_schedule", "register_skill",
]


class PromptConfig(BaseModel):
    instructions: str = Field(default="", max_length=20000)  # 에이전트의 역할·말투·절차 지침
    starters: List[str] = Field(default_factory=list, max_length=4)  # 새 대화 화면의 추천 질문

    @field_validator("starters")
    @classmethod
    def _starters(cls, v):
        return [s.strip()[:200] for s in v if s and s.strip()]


class ModelConfig(BaseModel):
    llm_provider: Optional[str] = None  # None 이면 사용자가 고른 값 / 서버 기본값
    model: Optional[str] = None
    max_iterations: Optional[int] = Field(default=None, ge=1, le=50)


class ToolsConfig(BaseModel):
    mode: Literal["all", "selected"] = "all"  # all: 기본 도구 전체, selected: allow 목록만
    allow: List[str] = Field(default_factory=list)


class SkillsConfig(BaseModel):
    mode: Literal["all", "selected", "none"] = "all"
    names: List[str] = Field(default_factory=list)


class McpServerRule(BaseModel):
    name: str
    allowed_tools: Optional[List[str]] = None  # None 이면 해당 서버의 모든 도구


class McpConfig(BaseModel):
    mode: Literal["all", "selected", "none"] = "all"
    servers: List[McpServerRule] = Field(default_factory=list)


class MemoryConfig(BaseModel):
    enabled: bool = True  # 사용자의 메모리 주입·자동 추출 사용 여부 (메모리는 에이전트가 아니라 사용자 것)


class SubAgentConfig(BaseModel):
    name: str
    role: str = Field(max_length=300)
    instructions: str = Field(default="", max_length=4000)
    tools: List[str] = Field(default_factory=list)  # 이 서브에이전트가 쓸 도구 (에이전트 전체 허용 도구의 부분집합)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        if not NAME_RE.match(v):
            raise ValueError("서브에이전트 이름은 영문/숫자/-/_ 로 40자 이내여야 합니다")
        return v


class TeamConfig(BaseModel):
    # default: 기본 팀(Research/Coder/Explorer 자동 구성), custom: 아래 members 만, none: 서브에이전트 없이 단독 실행
    mode: Literal["default", "custom", "none"] = "default"
    members: List[SubAgentConfig] = Field(default_factory=list, max_length=6)


class AgentConfig(BaseModel):
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    team: TeamConfig = Field(default_factory=TeamConfig)


class AgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="🤖", max_length=8)
    config: AgentConfig = Field(default_factory=AgentConfig)


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    icon: Optional[str] = Field(default=None, max_length=8)
    config: Optional[AgentConfig] = None


class PublishRequest(BaseModel):
    note: str = Field(default="", max_length=300)


class ValidationIssue(BaseModel):
    level: Literal["error", "warning"]
    path: str
    message: str


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    config: AgentConfig  # 초안
    published_version: Optional[int] = None
    published_at: Optional[datetime] = None
    has_unpublished_changes: bool = False
    created_at: datetime
    updated_at: datetime


class AgentSummary(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    published_version: Optional[int] = None
    has_unpublished_changes: bool = False
    starters: List[str] = []
    updated_at: datetime


class VersionResponse(BaseModel):
    id: str
    version: int
    note: str
    config: AgentConfig
    created_at: datetime
    is_current: bool = False


class SaveResult(BaseModel):
    agent: AgentResponse
    issues: List[ValidationIssue] = []


class ToolInfo(BaseModel):
    name: str
    description: str
    group: str
    risk: Literal["read", "write", "exec"]


class SkillInfo(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class McpServerInfo(BaseModel):
    name: str
    display_name: str
    transport: str
    tools: List[str] = []  # 현재 연결돼 있으면 도구 이름 목록 (연결 전이면 빈 목록)


class CatalogResponse(BaseModel):
    tools: List[ToolInfo]
    skills: List[SkillInfo]
    mcp_servers: List[McpServerInfo]
    llm_providers: List[str]

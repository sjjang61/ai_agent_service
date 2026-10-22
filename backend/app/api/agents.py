"""커스텀 에이전트 API: 목록·생성·수정·삭제·복제, 발행·버전·롤백, 설정 검증, 선택 가능한 자원 카탈로그."""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.agent import (
    AgentConfig,
    AgentInput,
    AgentResponse,
    AgentSummary,
    AgentUpdate,
    CatalogResponse,
    McpServerInfo,
    PublishRequest,
    SaveResult,
    SkillInfo,
    ToolInfo,
    ValidationIssue,
    VersionResponse,
)
from app.services.agent_service import KNOWN_PROVIDERS, AgentService

router = APIRouter()

# 선택 가능한 도구 카탈로그: (설명, 그룹, 위험도) — read: 읽기·조회, write: 파일·데이터·예약 변경, exec: 코드·명령·브라우저 실행
TOOL_CATALOG = {
    "web_search": ("웹에서 최신 정보를 검색합니다.", "검색·수집", "read"),
    "web_crawler": ("웹 페이지의 본문을 추출합니다.", "검색·수집", "read"),
    "search_documents": ("업로드한 문서(RAG)에서 관련 내용을 찾습니다.", "검색·수집", "read"),
    "search_wiki": ("저장해 둔 개인 위키 문서에서 관련 내용을 찾습니다.", "검색·수집", "read"),
    "read_file": ("샌드박스의 파일을 읽습니다.", "파일", "read"),
    "grep_file": ("샌드박스 파일에서 문자열·패턴을 검색합니다.", "파일", "read"),
    "read_image": ("이미지를 분석합니다.", "파일", "read"),
    "write_file": ("샌드박스에 파일을 만들거나 덮어씁니다.", "파일", "write"),
    "edit_file": ("파일의 일부를 수정합니다.", "파일", "write"),
    "delete_file": ("샌드박스의 파일을 삭제합니다.", "파일", "write"),
    "download_file": ("URL의 파일을 샌드박스로 내려받습니다.", "파일", "write"),
    "publish_file": ("샌드박스 파일의 공개 다운로드 링크를 만듭니다.", "파일", "write"),
    "code_executor": ("샌드박스에서 코드를 실행합니다.", "실행", "exec"),
    "exec_command": ("샌드박스에서 셸 명령을 실행합니다.", "실행", "exec"),
    "cli_browser_agent": ("브라우저를 조작하는 작업을 수행합니다.", "실행", "exec"),
    "create_widget": ("표·차트·수치 카드·프로세스 다이어그램을 만듭니다.", "표현", "read"),
    "todo": ("작업 계획과 진행 상태를 관리합니다.", "상호작용", "read"),
    "narrate": ("진행 상황을 사용자에게 알립니다.", "상호작용", "read"),
    "form_ask_user": ("사용자에게 폼으로 질문하고 답을 받습니다.", "상호작용", "read"),
    "memory_tool": ("사용자 메모리를 저장·조회합니다.", "기억", "write"),
    "manage_schedule": ("채팅으로 예약 작업을 만들고 관리합니다.", "자동화", "write"),
    "register_skill": ("샌드박스에서 만든 스킬을 등록합니다.", "자동화", "write"),
}


@router.get("/catalog", response_model=CatalogResponse)
async def catalog(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """빌더에서 고를 수 있는 도구·스킬·MCP 서버."""
    from app.mcp.manager import MCPSessionManager
    from app.services.mcp_service import MCPService
    from app.services.skill_service import SkillService

    sessions = MCPSessionManager._sessions.get(user.id, {})
    mcp = []
    for c in await MCPService.get_user_configs(user.id, db):
        client = sessions.get(c.name)  # 연결돼 있을 때만 도구 이름을 알 수 있다 (여기서 새로 연결하지 않는다)
        mcp.append(McpServerInfo(
            name=c.name, display_name=c.display_name or c.name, transport=c.transport,
            tools=[t.name for t in (getattr(client, "_tools", None) or [])],
        ))
    return CatalogResponse(
        tools=[ToolInfo(name=n, description=d, group=g, risk=r) for n, (d, g, r) in TOOL_CATALOG.items()],
        skills=[SkillInfo(name=s.name, description=s.description, is_active=bool(s.is_active)) for s in await SkillService.list_skills(user.id, db)],
        mcp_servers=mcp,
        llm_providers=sorted(KNOWN_PROVIDERS),
    )


@router.post("/validate", response_model=List[ValidationIssue])
async def validate_config(config: AgentConfig, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await AgentService.validate(user.id, config, db)


@router.get("", response_model=List[AgentSummary])
async def list_agents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return [await AgentService.to_summary(a, db) for a in await AgentService.list_agents(user.id, db)]


@router.post("", response_model=SaveResult)
async def create_agent(data: AgentInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    agent = await AgentService.create(user.id, data, db)
    return SaveResult(agent=await AgentService.to_response(agent, db), issues=await AgentService.validate(user.id, data.config, db))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await AgentService.to_response(await AgentService.get(user.id, agent_id, db), db)


@router.put("/{agent_id}", response_model=SaveResult)
async def update_agent(agent_id: str, data: AgentUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """초안을 저장한다 (발행된 버전은 바뀌지 않는다)."""
    agent = await AgentService.update(user.id, agent_id, data, db)
    resp = await AgentService.to_response(agent, db)
    return SaveResult(agent=resp, issues=await AgentService.validate(user.id, resp.config, db))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await AgentService.delete(user.id, agent_id, db)
    return {"status": "deleted"}


@router.post("/{agent_id}/duplicate", response_model=AgentResponse)
async def duplicate_agent(agent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await AgentService.to_response(await AgentService.duplicate(user.id, agent_id, db), db)


@router.post("/{agent_id}/publish", response_model=SaveResult)
async def publish_agent(agent_id: str, data: PublishRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """현재 초안을 새 버전으로 발행한다. 새 대화와 예약은 발행된 버전으로 실행된다."""
    _, issues = await AgentService.publish(user.id, agent_id, data.note, db)
    agent = await AgentService.get(user.id, agent_id, db)
    return SaveResult(agent=await AgentService.to_response(agent, db), issues=issues)


@router.get("/{agent_id}/versions", response_model=List[VersionResponse])
async def list_versions(agent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await AgentService.versions(user.id, agent_id, db)


@router.post("/{agent_id}/versions/{version}/restore", response_model=AgentResponse)
async def restore_version(agent_id: str, version: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """이전 버전의 설정을 초안으로 불러온다."""
    return await AgentService.to_response(await AgentService.restore_version_to_draft(user.id, agent_id, version, db), db)


@router.post("/{agent_id}/versions/{version}/activate", response_model=AgentResponse)
async def activate_version(agent_id: str, version: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """롤백: 이전 버전을 현재 발행 버전으로 되돌린다."""
    return await AgentService.to_response(await AgentService.set_current_version(user.id, agent_id, version, db), db)

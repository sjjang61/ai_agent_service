import logging
from typing import AsyncIterator, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import ConversationMemory
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.streaming import AgentStreamingHandler
from app.config import normalize_llm_type, settings
from app.tools.skill_tool import RegisterSkillTool, build_skills_prompt

logger = logging.getLogger(__name__)


def _build_memory_context(long_term: List, short_term: dict) -> str:
    """Build memory context section for system prompt."""
    sections = []

    if long_term:
        items = []
        for m in long_term:
            items.append(f"- [{m.category}] {m.key}: {m.value}")
        sections.append(
            "## User Information (Long-term Memory)\n" + "\n".join(items)
        )

    if short_term:
        items = [f"- {k}: {v}" for k, v in short_term.items()]
        sections.append(
            "## Current Task Context (Short-term)\n" + "\n".join(items)
        )

    if sections:
        return "\n\n" + "\n\n".join(sections) + "\n\n"
    return ""


class AgentOrchestrator:
    def __init__(
        self,
        user_id: str,
        llm_provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.user_id = user_id
        self.llm_provider = normalize_llm_type(llm_provider or settings.LLM_TYPE)
        self.model = model or settings.default_model_for(self.llm_provider)

    async def _get_active_skills(self, db: AsyncSession) -> list:
        from app.services.skill_service import SkillService

        try:
            # 에이전트가 sandbox 에 만들어 두고 등록하지 않은 skill 을 자동 등록
            await SkillService.import_from_sandbox(self.user_id, db)
        except Exception:
            logger.exception("[skills] sandbox skill 자동 등록 실패")
        try:
            skills = await SkillService.list_skills(self.user_id, db)
        except Exception:
            return []
        return [s for s in skills if s.is_active]

    async def _get_tools(
        self, db: AsyncSession, skills: list, conversation_id: str = ""
    ) -> tuple[list, str]:
        """(에이전트 도구 목록, 시스템 프롬프트에 덧붙일 MCP 도구 목록)"""
        from app.tools import get_builtin_tools
        from app.tools.mcp_tools import (
            CallMcpToolTool, LoadMcpToolTool, RunMcpCodeTool, build_mcp_catalog_prompt,
        )
        from app.tools.browser_tools import CliBrowserAgentTool
        from app.tools.interaction_tools import FormAskUserTool, NarrateTool, TodoTool
        from app.tools.skill_tool import LoadSkillTool
        from app.tools.sub_agent_tool import CallSubAgentTool
        from app.mcp.manager import MCPSessionManager
        from app.db.session import get_session_context

        tools = await get_builtin_tools(
            self.user_id,
            conversation_id=conversation_id,
            db_session_factory=get_session_context,
        )
        tools.append(RegisterSkillTool(user_id=self.user_id))
        tools += [
            TodoTool(conversation_id=conversation_id),
            NarrateTool(),
            FormAskUserTool(user_id=self.user_id, conversation_id=conversation_id),
            CliBrowserAgentTool(user_id=self.user_id, llm_provider=self.llm_provider, model=self.model),
        ]
        if skills:
            tools.append(LoadSkillTool(skills={s.name: s.install_path for s in skills}))

        mcp_prompt = ""
        if settings.MCP_TOOL_MODE == "lazy":
            # 스키마 전체를 싣지 않고 load_mcp_tool / call_mcp_tool / run_mcp_code 로 필요할 때만 조회·호출
            try:
                clients = await MCPSessionManager.get_clients(self.user_id, db)
            except Exception:
                clients = {}
            if clients:
                tools += [
                    LoadMcpToolTool(user_id=self.user_id),
                    CallMcpToolTool(user_id=self.user_id),
                    RunMcpCodeTool(user_id=self.user_id),
                ]
                mcp_prompt = build_mcp_catalog_prompt(clients)
        else:
            try:
                tools += await MCPSessionManager.get_tools(self.user_id, db)
            except Exception:
                pass

        # 서브에이전트는 call_sub_agent 를 제외한 도구를 사용한다 (재귀 위임 방지)
        tools.append(
            CallSubAgentTool(tools=list(tools), llm_provider=self.llm_provider, model=self.model)
        )
        return tools, mcp_prompt

    async def run(
        self, user_input: str, conversation_id: str, db: AsyncSession
    ) -> AsyncIterator[dict]:
        from app.services.chat_service import ChatService
        from app.services.memory_service import MemoryService, ShortTermMemoryService
        from app.tools.interaction_tools import complete_all_todos

        print(f"\n{'='*80}")
        print(f"[ORCHESTRATOR RUN] 새 요청 시작")
        print(f"  conversation_id: {conversation_id}")
        print(f"  user_input: {user_input[:200]}")
        print(f"{'='*80}\n")
        logger.info(f"[orchestrator] 새 요청 시작 - conversation_id: {conversation_id[:8]}..., user_input: {user_input[:100]}")

        # 새 요청 시작 시 이전 작업의 미완료 todo를 모두 completed로 변경
        # 이전 대화가 컨텍스트로 포함되더라도 이전 작업을 다시 수행하지 않도록 함
        complete_all_todos(conversation_id)

        messages = await ChatService.get_messages(conversation_id, db)
        logger.info(f"[orchestrator] 대화 기록 로드: {len(messages)}개 메시지")

        memory = ConversationMemory.from_db_messages(messages)

        logger.info(f"[orchestrator] 메모리 구성: {len(memory.get_messages())}개 메시지 (최근 20개)")

        # 디버깅: 메모리에 포함된 메시지 로깅
        for i, msg in enumerate(memory.get_messages()[-5:]):  # 최근 5개만
            role = "user" if msg.__class__.__name__ == "HumanMessage" else ("system" if msg.__class__.__name__ == "SystemMessage" else "assistant")
            logger.info(f"  [{i}] {role}: {msg.content[:100]}...")

        # Load user memories for context injection
        try:
            long_term_memories = await MemoryService.get_context_memories(
                self.user_id, db, limit=15
            )
        except Exception:
            long_term_memories = []

        try:
            short_term_memories = await ShortTermMemoryService.get_all(
                self.user_id, conversation_id
            )
        except Exception:
            short_term_memories = {}

        memory_context = _build_memory_context(long_term_memories, short_term_memories)

        skills = await self._get_active_skills(db)
        tools, mcp_prompt = await self._get_tools(db, skills, conversation_id)
        system_prompt = SYSTEM_PROMPT + memory_context + build_skills_prompt(skills) + mcp_prompt

        if settings.AGENT_ENGINE == "agno":
            from app.agent.agno_engine import AgnoRunner

            try:
                runner = AgnoRunner(tools, self.llm_provider, self.model, system_prompt)
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return
            async for event in runner.stream(
                user_input, memory.get_messages(), conversation_id, self.user_id, db=db
            ):
                yield event
            return

        handler = AgentStreamingHandler(
            tools=tools,
            llm_provider=self.llm_provider,
            model=self.model,
            system_prompt=system_prompt,
        )

        async for event in handler.stream(user_input, memory):
            yield event

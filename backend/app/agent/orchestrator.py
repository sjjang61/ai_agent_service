import logging
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import ConversationMemory
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.streaming import AgentStreamingHandler
from app.config import normalize_llm_type, settings
from app.tools.skill_tool import RegisterSkillTool, build_skills_prompt

logger = logging.getLogger(__name__)


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

    async def _get_tools(self, db: AsyncSession, skills: list, conversation_id: str = "") -> tuple[list, str]:
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

        tools = await get_builtin_tools(self.user_id)
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

        messages = await ChatService.get_messages(conversation_id, db)
        memory = ConversationMemory.from_db_messages(messages)

        skills = await self._get_active_skills(db)
        tools, mcp_prompt = await self._get_tools(db, skills, conversation_id)
        system_prompt = SYSTEM_PROMPT + build_skills_prompt(skills) + mcp_prompt

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

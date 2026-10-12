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

    async def _get_tools(self, db: AsyncSession, skills: list) -> list:
        from app.tools import get_builtin_tools
        from app.tools.skill_tool import ReadSkillTool
        from app.mcp.manager import MCPSessionManager

        builtin = await get_builtin_tools(self.user_id)
        builtin.append(RegisterSkillTool(user_id=self.user_id))
        if skills:
            builtin.append(ReadSkillTool(skills={s.name: s.install_path for s in skills}))
        try:
            mcp_tools = await MCPSessionManager.get_tools(self.user_id, db)
        except Exception:
            mcp_tools = []
        return builtin + mcp_tools

    async def run(
        self, user_input: str, conversation_id: str, db: AsyncSession
    ) -> AsyncIterator[dict]:
        from app.services.chat_service import ChatService

        messages = await ChatService.get_messages(conversation_id, db)
        memory = ConversationMemory.from_db_messages(messages)

        skills = await self._get_active_skills(db)
        tools = await self._get_tools(db, skills)
        handler = AgentStreamingHandler(
            tools=tools,
            llm_provider=self.llm_provider,
            model=self.model,
            system_prompt=SYSTEM_PROMPT + build_skills_prompt(skills),
        )

        async for event in handler.stream(user_input, memory):
            yield event

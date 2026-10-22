import logging
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import ConversationMemory
from app.agent.prompts import SYSTEM_PROMPT, load, render
from app.agent.streaming import AgentStreamingHandler
from app.config import normalize_llm_type, settings
from app.agent.agent_runtime import (
    AgentRuntime, compose_prompt, filter_skills, filter_tools, memory_enabled, mcp_enabled, resolve_model,
)
from app.tools.skill_tool import RegisterSkillTool, build_skills_prompt

logger = logging.getLogger(__name__)


def _build_memory_context(long_term: dict, short_term: dict) -> str:
    """시스템 프롬프트에 붙일 메모리 섹션.

    사실(semantic)은 참고 정보, 작업 방식(procedural)은 반드시 따를 지침, 사례(episodic)는
    현재 요청과 비슷한 과거 경험으로 역할을 구분해 넣는다.
    """
    sections = []

    facts = long_term.get("semantic") or []
    if facts:
        sections.append(render("memory_facts", items="\n".join(f"- {m.key}: {m.value}" for m in facts)))

    procedures = long_term.get("procedural") or []
    if procedures:
        sections.append(render("memory_procedures", items="\n".join(f"- {m.value}" for m in procedures)))

    episodes = long_term.get("episodic") or []
    if episodes:
        lines = []
        for m in episodes:
            d = m.detail or {}
            when = (m.occurred_at or m.created_at)
            head = f"- ({when.strftime('%Y-%m') if when else '시점 미상'}) {m.value}"
            parts = [f"{label}: {d[k]}" for k, label in (("situation", "상황"), ("resolution", "해결"), ("outcome", "결과")) if d.get(k)]
            lines.append(head + (" [" + " / ".join(parts) + "]" if parts else ""))
        sections.append(render("memory_episodes", items="\n".join(lines)))

    if short_term:
        sections.append(render("memory_short_term", items="\n".join(f"- {k}: {v}" for k, v in short_term.items())))

    if sections:
        return "\n\n" + "\n\n".join(sections) + "\n\n"
    return ""


def _valid_timezone(name: Optional[str]) -> str:
    """클라이언트가 보낸 시간대가 올바르지 않으면 기본 시간대로 대체한다."""
    from zoneinfo import ZoneInfo

    for cand in (name, settings.SCHEDULER_DEFAULT_TIMEZONE, "UTC"):
        try:
            if cand:
                ZoneInfo(cand)
                return cand
        except Exception:
            continue
    return "UTC"


def _time_context(tz_name: str) -> str:
    """'내일 9시' 같은 상대 표현을 해석할 수 있도록 현재 시각을 알려준다."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo(tz_name))
    weekday = "월화수목금토일"[now.weekday()]
    return "\n\n" + render("time_context", now=f"{now:%Y-%m-%d %H:%M} ({weekday}요일, {tz_name})") + "\n"


_restore_tasks: set = set()  # 실행 중인 복구 작업 (참조를 유지해 가비지 수집을 막는다)


def _spawn_sandbox_restore(user_id: str) -> None:
    import asyncio

    from app.services.sandbox_service import SandboxService

    async def _run():
        try:
            await SandboxService.restore_if_backed_up(user_id)
        except Exception:
            logger.exception("[sandbox] 요청 시작 시 복구 실패 — 도구 사용 시 다시 시도됩니다")

    task = asyncio.create_task(_run())
    _restore_tasks.add(task)
    task.add_done_callback(_restore_tasks.discard)


class AgentOrchestrator:
    def __init__(
        self,
        user_id: str,
        llm_provider: Optional[str] = None,
        model: Optional[str] = None,
        headless: bool = False,
        allow_mcp: bool = True,
        allow_browser: bool = True,
        user_timezone: Optional[str] = None,
        runtime: Optional["AgentRuntime"] = None,
    ):
        self.runtime = runtime  # 커스텀 에이전트 설정 (None 이면 기본 에이전트)
        self.user_timezone = _valid_timezone(user_timezone)
        self.headless = headless
        self.allow_mcp = allow_mcp and mcp_enabled(runtime)
        self.allow_browser = allow_browser
        self.user_id = user_id
        provider, model_id = resolve_model(runtime, llm_provider, model)
        self.llm_provider = normalize_llm_type(provider or settings.LLM_TYPE)
        self.model = model_id or settings.default_model_for(self.llm_provider)

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
        return filter_skills([s for s in skills if s.is_active], self.runtime)

    async def _get_tools(
        self, db: AsyncSession, skills: list, conversation_id: str = "", current_message: str = ""
    ) -> tuple[list, str]:
        """(에이전트 도구 목록, 시스템 프롬프트에 덧붙일 MCP 도구 목록)"""
        from app.tools import get_builtin_tools
        from app.tools.mcp_tools import (
            CallMcpToolTool, LoadMcpToolTool, RunMcpCodeTool, build_mcp_catalog_prompt,
        )
        from app.tools.browser_tools import CliBrowserAgentTool
        from app.tools.interaction_tools import FormAskUserTool, HeadlessAskUserTool, NarrateTool, TodoTool
        from app.tools.skill_tool import LoadSkillTool
        from app.tools.schedule_tool import ManageScheduleTool
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
            # 사용자가 없는 실행에서는 응답을 기다리며 멈추지 않도록 질문 도구를 대체한다
            HeadlessAskUserTool()
            if self.headless
            else FormAskUserTool(user_id=self.user_id, conversation_id=conversation_id),
        ]
        if not self.headless:
            # 예약 실행 안에서는 새 예약을 만들 수 없다 (예약이 예약을 만드는 연쇄 방지)
            tools.append(ManageScheduleTool(
                user_id=self.user_id, default_timezone=self.user_timezone, current_message=current_message
            ))
        if self.allow_browser:
            tools.append(
                CliBrowserAgentTool(user_id=self.user_id, llm_provider=self.llm_provider, model=self.model)
            )
        if skills:
            tools.append(LoadSkillTool(skills={s.name: s.install_path for s in skills}, user_id=self.user_id))

        mcp_prompt = ""
        if not self.allow_mcp:
            pass  # 예약 작업은 작업별로 MCP 사용을 허용한 경우에만 MCP 도구를 노출한다
        elif settings.MCP_TOOL_MODE == "lazy":
            # 스키마 전체를 싣지 않고 load_mcp_tool / call_mcp_tool / run_mcp_code 로 필요할 때만 조회·호출
            from app.mcp.policy import apply_policy, policy_from_config

            policy = policy_from_config(self.runtime.config.mcp) if self.runtime else None
            try:
                clients = apply_policy(await MCPSessionManager.get_clients(self.user_id, db), policy)
            except Exception:
                clients = {}
            if clients:
                tools += [
                    LoadMcpToolTool(user_id=self.user_id, mcp_policy=policy),
                    CallMcpToolTool(user_id=self.user_id, mcp_policy=policy),
                    RunMcpCodeTool(user_id=self.user_id, mcp_policy=policy),
                ]
                mcp_prompt = build_mcp_catalog_prompt(clients)
        else:
            try:
                if self.runtime and self.runtime.config.mcp.mode != "all":
                    from app.mcp.policy import apply_policy, policy_from_config

                    clients = apply_policy(
                        await MCPSessionManager.get_clients(self.user_id, db), policy_from_config(self.runtime.config.mcp)
                    )
                    for c in clients.values():
                        tools += c.to_langchain_tools()
                else:
                    tools += await MCPSessionManager.get_tools(self.user_id, db)
            except Exception:
                pass

        # 커스텀 에이전트의 도구 허용 목록 적용
        tools = filter_tools(tools, self.runtime)

        # 서브에이전트는 call_sub_agent 를 제외한 도구를 사용한다 (재귀 위임 방지)
        tools.append(
            CallSubAgentTool(tools=list(tools), llm_provider=self.llm_provider, model=self.model)
        )
        if self.runtime and self.runtime.config.tools.mode == "selected":
            tools = [t for t in tools if t.name != "call_sub_agent"]
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

        # 이 세션의 sandbox 가 유휴로 백업·종료된 상태면 요청이 시작되는 즉시 MinIO 백업에서 복구한다 (백그라운드).
        # sandbox 도구가 필요하면 같은 락을 쓰므로 복구가 끝날 때까지 기다린다.
        _spawn_sandbox_restore(self.user_id)

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

        # 응답 전에 요청을 가른다: 서술(짧은 반응으로 끝) / 단순(바로 처리) / 복잡(전체 작업 계획을 먼저 만들어 보여 준 뒤 실행)
        from app.agent.router import prior_history, route_request, should_route
        from app.tools.interaction_tools import seed_todos

        route_note = ""
        if should_route(user_input, self.headless):
            earlier = prior_history(memory.get_messages(), user_input)
            route = await route_request(user_input, earlier)
            logger.info("[orchestrator] 요청 분류: %s (계획 %d단계)", route.kind, len(route.plan))
            if route.kind == "statement":
                yield {"type": "token", "content": route.reply}
                return
            if route.kind == "complex":
                todos, output = seed_todos(conversation_id, route.plan)
                yield {"type": "tool_call", "tool": "todo", "input": {"action": "write", "todos": todos}}
                yield {"type": "tool_result", "tool": "todo", "output": output}
                route_note = "\n\n" + render(
                    "plan_context", plan="\n".join(f"{t['id']}. {t['content']}" for t in todos)
                )
            else:
                route_note = "\n\n" + load("route_simple")

        # Load user memories for context injection (에이전트 설정에서 끌 수 있다. 메모리는 에이전트가 아니라 사용자 것이다)
        long_term_memories: dict = {}
        short_term_memories: dict = {}
        if memory_enabled(self.runtime):
            try:
                long_term_memories = await MemoryService.get_prompt_memories(
                    self.user_id, db, user_input
                )
            except Exception:
                logger.exception("[orchestrator] 장기 메모리 로드 실패")

            try:
                short_term_memories = await ShortTermMemoryService.get_all(
                    self.user_id, conversation_id
                )
            except Exception:
                short_term_memories = {}

        memory_context = _build_memory_context(long_term_memories, short_term_memories)
        try:
            from app.models.conversation import Conversation
            from app.services.conversation_summary import summary_context

            conv = await db.get(Conversation, conversation_id)
            memory_context += summary_context(conv.summary if conv else None, len(messages))
        except Exception:
            logger.exception("[orchestrator] 대화 요약 로드 실패")

        skills = await self._get_active_skills(db)
        tools, mcp_prompt = await self._get_tools(db, skills, conversation_id, user_input)
        system_prompt = compose_prompt(SYSTEM_PROMPT, self.runtime) + _time_context(self.user_timezone) + memory_context + build_skills_prompt(skills) + mcp_prompt + route_note + ("\n\n" + load("headless") if self.headless else "")

        if settings.AGENT_ENGINE == "agno":
            from app.agent.agno_engine import AgnoRunner

            try:
                runner = AgnoRunner(
                    tools, self.llm_provider, self.model, system_prompt,
                    team_cfg=self.runtime.config.team if self.runtime else None,
                    max_iterations=self.runtime.config.model.max_iterations if self.runtime else None,
                )
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

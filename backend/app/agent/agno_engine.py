"""Agno Team 기반 멀티에이전트 실행 엔진.

구성 (coordinate 모드)
  Leader (TeamLead) : 요청 분석·위임·결과 통합
  ├─ ResearchAgent  : web_search, web_crawler
  ├─ CoderAgent     : code_executor, exec_command, read/write/edit/grep/delete/download/publish_file, read_image
  └─ ExplorerAgent  : read_file, grep_file, exec_command (읽기 전용 탐색)
  Leader 도구: load_skill, register_skill, memory_tool, read_image, create_widget, load_mcp_tool/call_mcp_tool/run_mcp_code,
               todo, narrate, form_ask_user, cli_browser_agent

기존 LangChain BaseTool(내장 도구, MCP 도구)을 agno Function 으로 감싸서 그대로 재사용하고,
Agno 이벤트를 기존 WebSocket/SSE 프로토콜(token / tool_call / tool_result / error)로 변환한다.
"""
import json
import logging
from typing import Any, AsyncIterator, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import agent_spec, load, render, sections
from app.config import normalize_llm_type, settings

logger = logging.getLogger(__name__)

RESEARCH_TOOLS = {"web_search", "web_crawler"}
# file_manager / shell_executor 는 read_file·write_file·… / exec_command 로 대체되어 Team 에서는 제외한다
CODER_TOOLS = {
    "code_executor", "exec_command", "read_file", "write_file", "edit_file", "grep_file",
    "delete_file", "download_file", "publish_file", "read_image",
}
EXPLORER_TOOLS = {"read_file", "grep_file", "exec_command"}
MCP_TOOLS = {"load_mcp_tool", "call_mcp_tool", "run_mcp_code"}
INTERACTION_TOOLS = {"todo", "narrate", "form_ask_user", "cli_browser_agent", "manage_schedule"}
LEADER_TOOLS = {"load_skill", "register_skill", "memory_tool", "read_image", "create_widget", "search_documents", "search_wiki"} | MCP_TOOLS | INTERACTION_TOOLS
LEGACY_TOOLS = {"file_manager", "shell_executor"}
# Team 에서는 위임이 delegate_task_to_member 로 이미 제공되므로 call_sub_agent 는 제외한다
TEAM_EXCLUDED = {"call_sub_agent"}

# 서브에이전트 정의: Team 의 멤버와 call_sub_agent 가 공유한다
def _spec(key: str, name: str, tools: set) -> dict:
    role, instructions = agent_spec(f"subagent_{key}")  # prompts/subagent_<key>.md: 첫 문단=역할, 나머지=지침
    return dict(name=name, role=role, tools=tools, instructions=instructions)


AGENT_SPECS = {
    "research": _spec("research", "ResearchAgent", RESEARCH_TOOLS),
    "coder": _spec("coder", "CoderAgent", CODER_TOOLS),
    "explorer": _spec("explorer", "ExplorerAgent", EXPLORER_TOOLS),
}
MAX_TOOL_OUTPUT = 20000


# ── 모델 ─────────────────────────────────────────────────────────────────────
def build_agno_model(llm_type: str, model: Optional[str] = None):
    t = normalize_llm_type(llm_type)
    model_id = model or settings.default_model_for(t)
    if t == "pet":
        from agno.models.openai import OpenAILike

        if not settings.PET_AGENT_URL:
            raise ValueError("PET_AGENT_URL이 설정되지 않았습니다.")
        return OpenAILike(
            id=settings.PET_MODEL_ID,
            base_url=settings.PET_AGENT_URL,
            api_key=settings.PET_API_KEY,
            timeout=settings.PET_TIMEOUT,
            reasoning_effort=settings.PET_REASONING_EFFORT or None,
        )
    if t == "openai":
        from agno.models.openai import OpenAIChat

        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return OpenAIChat(
            id=model_id,
            api_key=settings.OPENAI_API_KEY,
            reasoning_effort=settings.OPENAI_REASONING_EFFORT or None,
        )
    if t == "gemini":
        from agno.models.google import Gemini

        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")
        return Gemini(id=model_id, api_key=settings.GOOGLE_API_KEY)
    if t == "anthropic":
        from agno.models.anthropic import Claude

        if not settings.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        return Claude(id=model_id, api_key=settings.ANTHROPIC_API_KEY)
    raise ValueError(f"Unknown LLM_TYPE: {llm_type} (pet | openai | gemini | anthropic)")


# ── 도구 변환: LangChain BaseTool → agno Function ────────────────────────────
def _json_schema(tool: BaseTool) -> dict:
    try:
        schema = tool.tool_call_schema.model_json_schema()  # type: ignore[union-attr]
    except Exception:
        schema = {"type": "object", "properties": {}}
    schema.pop("title", None)
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    return schema


def to_agno_function(tool: BaseTool):
    from agno.tools.function import Function

    async def _entrypoint(**kwargs: Any) -> str:
        try:
            out = await tool.ainvoke(kwargs)
        except Exception as e:  # 도구 오류는 LLM 이 볼 수 있도록 문자열로 반환
            return f"[Tool Error] {type(e).__name__}: {e}"
        out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
        return out[:MAX_TOOL_OUTPUT]

    return Function(
        name=tool.name,
        description=tool.description or tool.name,
        parameters=_json_schema(tool),
        entrypoint=_entrypoint,
        skip_entrypoint_processing=True,
    )


def _pick(tools: List[BaseTool], names: set) -> list:
    return [to_agno_function(t) for t in tools if t.name in names]


# ── Team / 서브에이전트 구성 ─────────────────────────────────────────────────
def make_agent(spec_key: str, tools: List[BaseTool], llm_type: str, model: Optional[str]):
    """AGENT_SPECS 의 서브에이전트를 만든다. 사용할 수 있는 도구가 하나도 없으면 None."""
    from agno.agent import Agent

    spec = AGENT_SPECS[spec_key]
    fns = _pick(tools, spec["tools"])
    if not fns:
        return None
    return Agent(
        name=spec["name"],
        role=spec["role"],
        model=build_agno_model(llm_type, model),
        tools=fns,
        tool_call_limit=settings.AGENT_MAX_ITERATIONS,
        instructions=spec["instructions"],
    )


def build_team(
    tools: List[BaseTool],
    llm_type: str,
    model: Optional[str],
    instructions: str,
    team_cfg=None,
    max_iterations: Optional[int] = None,
):
    """Team 구성. team_cfg(TeamConfig) 가 없거나 mode=default 이면 기본 팀(Research/Coder/Explorer),
    custom 이면 사용자가 정의한 서브에이전트만, none 이면 서브에이전트 없이 리더 단독으로 실행한다."""
    from agno.agent import Agent
    from agno.team import Team

    limit = max_iterations or settings.AGENT_MAX_ITERATIONS
    tools = [t for t in tools if t.name not in TEAM_EXCLUDED]
    mode = team_cfg.mode if team_cfg else "default"
    base_prompt = instructions

    def team_prompt(rule_file: str, *extra: str) -> list:
        """Agno 는 instructions 목록을 '- 항목' 줄로 이어 붙여서, 규칙이 별도 항목으로 있으면 바로 앞의 스킬 목록 끝에
        이어진 항목(스킬)처럼 보인다. 그래서 하나의 지침 문자열로 합치고 규칙에는 제목을 붙인다."""
        rules = "\n".join(f"- {r}" for r in [*sections(rule_file), *extra])
        return [base_prompt + "\n\n" + render("team_rules", rules=rules)]

    if mode == "default":
        known = RESEARCH_TOOLS | CODER_TOOLS | EXPLORER_TOOLS | LEADER_TOOLS | LEGACY_TOOLS
        mcp_direct = [t for t in tools if t.name not in known]  # AGENT mcp 모드가 direct 일 때의 개별 MCP 도구

        members = [m for m in (make_agent(k, tools, llm_type, model) for k in AGENT_SPECS) if m is not None]
        if mcp_direct:
            members.append(Agent(
                name="McpAgent",
                role="사용자가 등록한 외부 MCP 도구(" + ", ".join(t.name for t in mcp_direct[:8]) + " 등)를 사용하는 전문가",
                model=build_agno_model(llm_type, model), tools=[to_agno_function(t) for t in mcp_direct],
                tool_call_limit=limit,
            ))
        leader_tools = _pick(tools, LEADER_TOOLS)
        team_instructions = team_prompt("team_default")
    else:
        by_name = {t.name: t for t in tools}
        members, assigned = [], set()
        for m in (team_cfg.members if mode == "custom" else []):
            fns = [to_agno_function(by_name[n]) for n in m.tools if n in by_name]
            assigned |= {n for n in m.tools if n in by_name}
            members.append(Agent(
                name=m.name,
                role=m.role,
                model=build_agno_model(llm_type, model),
                tools=fns,
                tool_call_limit=limit,
                instructions=[m.instructions] if m.instructions.strip() else None,
            ))
        # 리더는 서브에이전트에게 배정되지 않은 모든 허용 도구를 직접 사용한다
        leader_tools = [to_agno_function(t) for t in tools if t.name not in assigned]
        team_instructions = team_prompt("team_custom", *([load("team_custom_delegate")] if members else []))

    return Team(
        name="AgentTeam",
        mode="coordinate",
        model=build_agno_model(llm_type, model),
        members=members,
        tools=leader_tools,
        tool_call_limit=limit,
        instructions=team_instructions,
        markdown=True,
    )


# ── 이벤트 변환 ──────────────────────────────────────────────────────────────
def _history_to_agno(messages: List[BaseMessage]) -> list:
    from agno.models.message import Message

    out = []
    for m in messages:
        if isinstance(m, (HumanMessage, AIMessage)) and isinstance(m.content, str) and m.content:
            out.append(Message(role="user" if isinstance(m, HumanMessage) else "assistant", content=m.content))
    return out


def _tool_origin(tool, ev=None) -> dict:
    """호출을 식별하는 call_id 와, 팀원이 한 호출이면 그 팀원 이름(agent). 화면이 부모(위임)-자식 묶음과 호출·결과 짝짓기에 쓴다."""
    out: dict = {}
    if getattr(tool, "tool_call_id", None):
        out["call_id"] = str(tool.tool_call_id)
    agent = getattr(ev, "agent_name", None) if ev is not None else None
    if agent:
        out["agent"] = str(agent)
    return out


def _tool_call_event(tool, ev=None) -> dict:
    return {"type": "tool_call", "tool": tool.tool_name or "", "input": tool.tool_args or {}, **_tool_origin(tool, ev)}


def _tool_result_event(tool, error: Optional[str] = None, ev=None) -> dict:
    output = error if error else str(tool.result if tool.result is not None else "")
    return {
        "type": "tool_result",
        "tool": tool.tool_name or "",
        "output": output[:MAX_TOOL_OUTPUT],
        "success": not (error or tool.tool_call_error or output.startswith(("[MCP Error]", "[Tool Error]"))),
        **_tool_origin(tool, ev),
    }


def _use_streaming(llm_type: str) -> bool:
    return settings.PET_STREAMING if normalize_llm_type(llm_type) == "pet" else True


def _extract_metrics(obj) -> tuple[int, int]:
    """Agno RunOutput 또는 이벤트에서 input_tokens, output_tokens 추출."""
    metrics = getattr(obj, "metrics", None)
    if not metrics:
        return 0, 0
    input_tokens = getattr(metrics, "input_tokens", 0) or 0
    output_tokens = getattr(metrics, "output_tokens", 0) or 0
    return input_tokens, output_tokens


async def stream_team(
    team,
    user_input: str,
    history: List[BaseMessage],
    session_id: str,
    user_id: str,
    streaming: bool,
    db: Optional[AsyncSession] = None,
    llm_provider: str = "",
    model: str = "",
) -> AsyncIterator[dict]:

    # 호출 전에 사용자 메시지가 이미 DB(=history)에 저장되므로 중복 제거
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_input:
        history = history[:-1]
    from app.agent.scope import with_scope_reminder

    # 이전 대화는 input 이 아니라 additional_input 으로 넘긴다.
    # Team.arun(input=[Message...]) 은 리더에게 user 메시지만 이어 붙인 한 덩어리 텍스트로 전달해 assistant 답변이 사라지므로
    # 매 턴마다 이전 질문에 모두 다시 답하게 된다 (예: "서울", "스킬 없음", "현재 시각"을 누적해서 반복).
    # additional_input 은 system 뒤에 user/assistant 턴을 그대로 이어 붙인다.
    team.additional_input = _history_to_agno(history) or None
    kwargs = dict(
        input=with_scope_reminder(user_input, bool(history)),
        user_id=user_id,
        session_id=session_id,
    )

    total_input_tokens = 0
    total_output_tokens = 0

    if not streaming:
        # 스트리밍 미지원 LLM: 완료 후 결과(RunOutput)에서 이벤트를 재구성한다
        out = await team.arun(**kwargs, stream=False)
        inp, outp = _extract_metrics(out)
        total_input_tokens += inp
        total_output_tokens += outp
        for ev in _events_from_output(out):
            yield ev
    else:
        got_token = False
        async for ev in team.arun(**kwargs, stream=True, stream_events=True):
            name = getattr(ev, "event", "")
            if name == "TeamRunContent":  # 리더의 응답 토큰 (멤버의 RunContent 는 중간 결과라 제외)
                c = getattr(ev, "content", None)
                if isinstance(c, str) and c:
                    got_token = True
                    yield {"type": "token", "content": c}
            elif name in ("ToolCallStarted", "TeamToolCallStarted") and ev.tool:
                yield _tool_call_event(ev.tool, ev)
            elif name in ("ToolCallCompleted", "TeamToolCallCompleted") and ev.tool:
                yield _tool_result_event(ev.tool, ev=ev)
            elif name in ("ToolCallError", "TeamToolCallError") and ev.tool:
                yield _tool_result_event(ev.tool, error=getattr(ev, "error", None) or "tool error", ev=ev)
            elif name in ("RunError", "TeamRunError"):
                yield {"type": "error", "message": getattr(ev, "content", None) or "Agent run failed"}
                return
            elif name in ("TeamRunCompleted", "RunCompleted"):
                inp, outp = _extract_metrics(ev)
                total_input_tokens += inp
                total_output_tokens += outp
        if not got_token:
            logger.warning("[agno] 응답 토큰이 없습니다")

    # 토큰 사용량 기록
    if db and (total_input_tokens > 0 or total_output_tokens > 0):
        try:
            from app.services.token_usage_service import TokenUsageService
            await TokenUsageService.record_usage(
                db=db,
                user_id=user_id,
                conversation_id=session_id,
                llm_provider=llm_provider,
                model_name=model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )
        except Exception:
            logger.exception("[agno] 토큰 사용량 기록 실패")


def _events_from_output(out) -> list:
    events: list = []

    def collect(run):
        for t in (getattr(run, "tools", None) or []):
            events.append(_tool_call_event(t, run))
            events.append(_tool_result_event(t, ev=run))

    for member in (getattr(out, "member_responses", None) or []):
        collect(member)
    collect(out)
    content = getattr(out, "content", None)
    if getattr(out, "status", None) and str(getattr(out.status, "value", out.status)).lower() == "error":
        events.append({"type": "error", "message": str(content or "Agent run failed")})
    elif isinstance(content, str) and content:
        events.append({"type": "token", "content": content})
    return events


class AgnoRunner:
    def __init__(
        self,
        tools: List[BaseTool],
        llm_provider: str,
        model: Optional[str],
        system_prompt: str,
        team_cfg=None,
        max_iterations: Optional[int] = None,
    ):
        self.llm_type = normalize_llm_type(llm_provider)
        self.llm_provider = llm_provider
        self.model = model or settings.default_model_for(self.llm_type)
        self.team = build_team(tools, self.llm_type, model, system_prompt, team_cfg, max_iterations)

    async def stream(
        self,
        user_input: str,
        history: List[BaseMessage],
        conversation_id: str,
        user_id: str,
        db: Optional[AsyncSession] = None,
    ) -> AsyncIterator[dict]:
        try:
            async for ev in stream_team(
                self.team,
                user_input,
                history,
                conversation_id,
                user_id,
                _use_streaming(self.llm_type),
                db=db,
                llm_provider=self.llm_provider,
                model=self.model,
            ):
                yield ev
        except Exception as e:
            logger.exception("[agno] 실행 실패")
            yield {"type": "error", "message": f"{type(e).__name__}: {e}"}

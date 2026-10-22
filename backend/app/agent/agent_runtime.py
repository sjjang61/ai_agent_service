"""커스텀 에이전트 설정(AgentConfig)을 실행에 반영하는 헬퍼.

AgentOrchestrator 가 이 모듈로 시스템 프롬프트 조합, 도구·스킬 필터링, 팀 구성을 한다.
에이전트가 없는 기본 실행(runtime=None)은 기존 동작과 완전히 같다.
"""
from dataclasses import dataclass
from typing import List, Optional

from app.agent.prompts import render
from app.schemas.agent import AgentConfig

# 도구 허용 목록(tools.mode=selected)과 무관하게 각 섹션(skills/mcp)이 따로 제어하는 도구
SECTION_CONTROLLED = {"load_skill", "load_mcp_tool", "call_mcp_tool", "run_mcp_code"}


@dataclass
class AgentRuntime:
    config: AgentConfig
    agent_id: str = ""
    agent_name: str = ""
    version: Optional[int] = None  # None 이면 초안(미리보기)


def compose_prompt(base: str, rt: Optional[AgentRuntime]) -> str:
    """기본 시스템 프롬프트 뒤에 에이전트 지침과 도구 제한 안내를 덧붙인다."""
    if rt is None:
        return base
    out = base
    text = rt.config.prompt.instructions.strip()
    if text:
        out += "\n\n" + render("custom_agent", name=rt.agent_name or "custom", instructions=text)
    if rt.config.tools.mode == "selected":
        allowed = ", ".join(rt.config.tools.allow) or "없음 (대화만 가능)"
        out += "\n\n" + render("tool_limit", allowed=allowed)
    return out


def filter_tools(tools: list, rt: Optional[AgentRuntime]) -> list:
    """tools.mode=selected 이면 허용 목록에 있는 도구(+ 스킬/MCP 섹션이 제어하는 도구)만 남긴다."""
    if rt is None or rt.config.tools.mode == "all":
        return tools
    allow = set(rt.config.tools.allow)
    return [t for t in tools if t.name in allow or t.name in SECTION_CONTROLLED]


def filter_skills(skills: list, rt: Optional[AgentRuntime]) -> list:
    if rt is None:
        return skills
    cfg = rt.config.skills
    if cfg.mode == "all":
        return skills
    if cfg.mode == "none":
        return []
    names = set(cfg.names)
    return [s for s in skills if s.name in names]


def mcp_enabled(rt: Optional[AgentRuntime]) -> bool:
    return rt is None or rt.config.mcp.mode != "none"


def memory_enabled(rt: Optional[AgentRuntime]) -> bool:
    return rt is None or rt.config.memory.enabled


def resolve_model(rt: Optional[AgentRuntime], provider: Optional[str], model: Optional[str]) -> tuple:
    """에이전트 설정 > 요청/대화 값 순으로 (provider, model) 을 정한다. provider 가 바뀌면 model 은 따로 지정된 경우만 쓴다."""
    if rt is None:
        return provider, model
    m = rt.config.model
    if m.llm_provider and m.llm_provider != provider:
        return m.llm_provider, m.model  # 다른 제공자의 모델명을 이어받지 않는다
    return provider, m.model or model


def member_tool_names(rt: Optional[AgentRuntime]) -> List[str]:
    if rt is None:
        return []
    return sorted({n for m in rt.config.team.members for n in m.tools})

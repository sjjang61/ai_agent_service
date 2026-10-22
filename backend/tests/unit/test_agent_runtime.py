from types import SimpleNamespace

import pytest

from app.agent import agno_engine
from app.agent.agent_runtime import (
    AgentRuntime, compose_prompt, filter_skills, filter_tools, mcp_enabled, memory_enabled, resolve_model,
)
from app.mcp.policy import apply_policy, policy_from_config
from app.schemas.agent import AgentConfig, McpConfig, McpServerRule, SubAgentConfig, TeamConfig
from app.services.agent_service import validate_config


def rt(**sections) -> AgentRuntime:
    return AgentRuntime(config=AgentConfig.model_validate(sections), agent_id="a1", agent_name="리서처")


def tool(name):
    return SimpleNamespace(name=name)


# ── 프롬프트 / 필터 ────────────────────────────────────────────────────────────
def test_compose_prompt_appends_custom_block_only_when_instructions_exist():
    assert compose_prompt("BASE", None) == "BASE"
    assert compose_prompt("BASE", rt()) == "BASE"
    out = compose_prompt("BASE", rt(prompt={"instructions": "항상 요약부터 쓴다"}))
    assert out.startswith("BASE") and "리서처" in out and "항상 요약부터 쓴다" in out
    # 도구를 제한하면 가능한 도구와 '하지 않은 일을 했다고 말하지 말 것' 안내가 붙는다
    limited = compose_prompt("BASE", rt(tools={"mode": "selected", "allow": ["web_search"]}))
    assert "web_search" in limited and "호출하지 않은 일" in limited and "역할과 지침" not in limited


def test_filter_tools_selected_keeps_allowed_and_section_controlled():
    tools = [tool(n) for n in ("web_search", "exec_command", "load_skill", "call_mcp_tool", "write_file")]
    assert filter_tools(tools, None) == tools
    assert filter_tools(tools, rt()) == tools
    got = [t.name for t in filter_tools(tools, rt(tools={"mode": "selected", "allow": ["web_search"]}))]
    assert got == ["web_search", "load_skill", "call_mcp_tool"]


def test_filter_skills_modes():
    skills = [SimpleNamespace(name=n) for n in ("pdf", "xlsx")]
    assert filter_skills(skills, rt()) == skills
    assert filter_skills(skills, rt(skills={"mode": "none"})) == []
    assert [s.name for s in filter_skills(skills, rt(skills={"mode": "selected", "names": ["xlsx", "nope"]}))] == ["xlsx"]


def test_flags_and_model_precedence():
    assert mcp_enabled(None) and memory_enabled(None)
    assert not mcp_enabled(rt(mcp={"mode": "none"})) and not memory_enabled(rt(memory={"enabled": False}))
    assert resolve_model(None, "openai", "gpt-x") == ("openai", "gpt-x")
    assert resolve_model(rt(model={"model": "gpt-y"}), "openai", "gpt-x") == ("openai", "gpt-y")
    # 제공자가 바뀌면 이전 제공자의 모델명을 이어받지 않는다
    assert resolve_model(rt(model={"llm_provider": "anthropic"}), "openai", "gpt-x") == ("anthropic", None)


# ── MCP 정책 ───────────────────────────────────────────────────────────────────
def fake_client(*names):
    return SimpleNamespace(_tools=[SimpleNamespace(name=n) for n in names])


def test_mcp_policy_filters_servers_and_tools_without_mutating_original():
    clients = {"fs": fake_client("read", "write"), "gh": fake_client("issue")}
    assert apply_policy(clients, None) is clients
    assert apply_policy(clients, policy_from_config(McpConfig(mode="none"))) == {}
    cfg = McpConfig(mode="selected", servers=[McpServerRule(name="fs", allowed_tools=["read"]), McpServerRule(name="nope")])
    out = apply_policy(clients, policy_from_config(cfg))
    assert list(out) == ["fs"] and [t.name for t in out["fs"]._tools] == ["read"]
    assert [t.name for t in clients["fs"]._tools] == ["read", "write"]  # 원본은 그대로


# ── 검증 ──────────────────────────────────────────────────────────────────────
def issues(cfg, skills=(), mcp=()):
    return [(i.level, i.path) for i in validate_config(cfg, set(skills), set(mcp))]


def test_validate_flags_unknown_tools_duplicates_and_subset_rule():
    cfg = AgentConfig(
        prompt={"instructions": "x"},
        tools={"mode": "selected", "allow": ["web_search", "bogus"]},
        team=TeamConfig(mode="custom", members=[
            SubAgentConfig(name="Dev", role="코더", tools=["web_search", "write_file"]),
            SubAgentConfig(name="dev", role="중복", tools=[]),
            SubAgentConfig(name="ResearchAgent", role="예약어"),
        ]),
    )
    got = issues(cfg)
    assert ("error", "tools.allow") in got  # bogus
    assert ("error", "team.members[0].tools") in got  # write_file 은 허용 목록에 없음
    assert ("error", "team.members[1].name") in got  # 대소문자 무시 중복
    assert ("error", "team.members[2].name") in got  # 예약된 이름


def test_validate_warnings_do_not_block():
    cfg = AgentConfig(skills={"mode": "selected", "names": ["ghost"]}, mcp={"mode": "selected", "servers": [{"name": "ghost"}]})
    got = issues(cfg, skills={"pdf"}, mcp={"fs"})
    assert all(level == "warning" for level, _ in got) and len(got) == 3  # 지침 비어 있음 + 스킬/MCP 미설치


def test_subagent_name_validation():
    with pytest.raises(ValueError):
        SubAgentConfig(name="bad name!", role="x")


# ── 팀 구성 (LLM 호출 없이 구조만 확인) ─────────────────────────────────────────
@pytest.fixture
def offline_models(monkeypatch):
    from agno.models.openai import OpenAIChat

    monkeypatch.setattr(agno_engine, "build_agno_model", lambda *_a, **_k: OpenAIChat(id="gpt-test", api_key="test"))
    monkeypatch.setattr(agno_engine, "to_agno_function", lambda t: SimpleNamespace(name=t.name))  # agno Function 변환 생략


class FakeTool:
    def __init__(self, name):
        self.name, self.description = name, f"{name} tool"
        self.args_schema = None

    def run(self, *a, **k): return ""


def _fn_names(fns):
    return sorted(getattr(f, "name", None) or f.__name__ for f in fns)


def build(offline, team_cfg, names=("web_search", "read_file", "write_file", "todo")):
    return agno_engine.build_team([FakeTool(n) for n in names], "openai", None, "BASE", team_cfg, max_iterations=7)


def test_team_none_has_no_members_and_leader_gets_all_tools(offline_models):
    team = build(offline_models, TeamConfig(mode="none"))
    assert team.members == [] and _fn_names(team.tools) == ["read_file", "todo", "web_search", "write_file"]


def test_team_custom_members_get_assigned_tools_and_leader_keeps_the_rest(offline_models):
    cfg = TeamConfig(mode="custom", members=[SubAgentConfig(name="Writer", role="문서 작성", instructions="짧게", tools=["write_file", "read_file"])])
    team = build(offline_models, cfg)
    assert [m.name for m in team.members] == ["Writer"]
    assert _fn_names(team.tools) == ["todo", "web_search"]  # 멤버에게 배정되지 않은 도구는 리더 몫


def test_team_default_keeps_builtin_members(offline_models):
    team = build(offline_models, None)
    assert {m.name for m in team.members} >= {"ResearchAgent", "CoderAgent", "ExplorerAgent"}

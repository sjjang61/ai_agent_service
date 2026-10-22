import json

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.router import STATEMENT_MAX_CHARS, _context, parse_route, prior_history, should_route, statement_allowed
from app.tools.interaction_tools import _todo_store, seed_todos

H = [HumanMessage(content="삼성전자 주가"), AIMessage(content="221,500원")]


def test_parse_statement_needs_reply_and_permission():
    r = parse_route('{"route": "statement", "reply": "테니스 좋아하시는군요!"}')
    assert (r.kind, r.reply) == ("statement", "테니스 좋아하시는군요!")
    assert parse_route('설명 {"route":"statement","reply":"네"} 끝').kind == "statement"
    assert parse_route('{"route": "statement", "reply": ""}').kind == "simple"  # 반응문이 없으면 에이전트에 맡긴다
    assert parse_route('{"route": "statement", "reply": "네"}', allow_statement=False).kind == "simple"


def test_parse_complex_needs_a_real_plan():
    r = parse_route('{"route": "complex", "plan": ["자료 조사", " ", "표로 정리", "답변 작성"]}')
    assert r.kind == "complex" and r.plan == ["자료 조사", "표로 정리", "답변 작성"]
    assert parse_route('{"route": "complex", "plan": ["하나뿐"]}').kind == "simple"
    assert parse_route('{"route": "complex"}').kind == "simple"
    assert len(parse_route('{"route": "complex", "plan": %s}' % json.dumps([f"단계{i}" for i in range(20)])).plan) == 8


def test_everything_else_is_simple():
    for text in ['{"route": "simple"}', '{"route": "other"}', "not json", "", "[1]", '{"route": 1}']:
        assert parse_route(text).kind == "simple", text


def test_routing_skipped_for_headless_and_empty():
    assert should_route("요약해줘", headless=False)
    assert not should_route("요약해줘", headless=True)  # 예약 실행
    assert not should_route("   ", headless=False)


def test_statement_only_with_history_and_short_message():
    assert statement_allowed("나는 테니스를 좋아해", H)
    assert not statement_allowed("나는 테니스를 좋아해", [])  # 첫 메시지
    assert not statement_allowed("가" * (STATEMENT_MAX_CHARS + 1), H)


def test_context_uses_recent_turns_only():
    hist = [HumanMessage(content=f"q{i}") if i % 2 == 0 else AIMessage(content=f"a{i}") for i in range(10)]
    ctx = _context(hist)
    assert "q6" in ctx and "a9" in ctx and "q0" not in ctx and ctx.count("\n") == 3


def test_prior_history_drops_the_current_message():
    cur = H + [HumanMessage(content="나는 테니스를 좋아해")]
    assert prior_history(cur, "나는 테니스를 좋아해") == H
    assert prior_history(H, "다른 메시지") == H
    assert prior_history([HumanMessage(content="첫 메시지")], "첫 메시지") == []


def test_seed_todos_first_step_in_progress_and_tool_start_completes_previous():
    import asyncio
    from app.tools.interaction_tools import TodoTool

    todos, out = seed_todos("c-test", ["조사", "정리", "답변"])
    assert [t["status"] for t in todos] == ["in_progress", "pending", "pending"]
    assert json.loads(out)["progress"] == "0/3"
    tool = TodoTool(conversation_id="c-test")
    res = json.loads(asyncio.run(tool._arun(action="start", id="2")))
    assert [t["status"] for t in res["todos"]] == ["completed", "in_progress", "pending"]
    assert res["progress"] == "1/3" and res["next"] == "정리"
    assert asyncio.run(tool._arun(action="start", id="9")).startswith("Error")
    _todo_store.pop("c-test", None)


def test_tool_events_carry_call_id_and_member_name():
    from types import SimpleNamespace as NS

    from app.agent.agno_engine import _tool_call_event, _tool_result_event

    tool = NS(tool_name="exec_command", tool_args={"command": "ls", "purpose": "목록"}, tool_call_id="call_1",
              result="ok", tool_call_error=False)
    member_ev = NS(agent_name="CoderAgent")
    assert _tool_call_event(tool, member_ev)["agent"] == "CoderAgent"
    assert _tool_call_event(tool, member_ev)["call_id"] == "call_1"
    assert "agent" not in _tool_call_event(tool, NS(team_name="AgentTeam"))  # 리더(팀) 호출에는 agent 가 없다
    assert _tool_result_event(tool, ev=member_ev)["call_id"] == "call_1"
    assert "call_id" not in _tool_call_event(NS(tool_name="x", tool_args=None, tool_call_id=None))


def test_wiki_draft_parsing():
    from app.services.wiki_draft import parse_draft

    ok = parse_draft('설명 {"title": " 2026 KBO  일정 ", "summary": "요약", "content": "## 핵심 정리\\n- a", "category": "bogus", "tags": ["#kbo", "kbo", "야구", ""]} 끝', "원문")
    assert ok.title == "2026 KBO 일정" and ok.category == "general" and ok.tags == ["kbo", "야구"]
    assert parse_draft('{"title": "", "content": "x"}', "원문") is None
    assert parse_draft('{"title": "t", "content": ""}', "원문") is None
    assert parse_draft("not json", "원문") is None


def test_wiki_match_and_related_section():
    from app.services.wiki_draft import parse_match, with_related_section

    valid = {"a", "b", "c"}
    assert parse_match('{"merge_into": "a", "related": ["a", "b", "zzz", "c"]}', valid) == ("a", ["b", "c"])
    assert parse_match('{"merge_into": "nope", "related": []}', valid) == (None, [])
    assert parse_match("not json", valid) == (None, [])
    body = "## 핵심 정리\n- x"
    out = with_related_section(body, ["문서 A", "문서 B"])
    assert out.endswith("## 관련 문서\n- [[문서 A]]\n- [[문서 B]]")
    again = with_related_section(out, ["문서 A", "문서 C"])  # 이미 있는 링크는 다시 붙이지 않는다
    assert again.count("[[문서 A]]") == 1 and again.endswith("- [[문서 C]]")
    assert with_related_section(body, []) == body


def test_empty_related_heading_is_removed():
    from app.services.wiki_draft import with_related_section

    assert with_related_section("## 상세\n내용\n\n## 관련 문서\n", []) == "## 상세\n내용"
    assert with_related_section("## 상세\n내용\n\n## 관련 문서\n", ["A"]).endswith("## 관련 문서\n- [[A]]")

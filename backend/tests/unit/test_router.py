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

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.intent import GATE_MAX_CHARS, _context, parse_intent, should_gate

H = [HumanMessage(content="삼성전자 주가"), AIMessage(content="221,500원")]


def test_parse_statement_returns_reply_and_everything_else_is_request():
    assert parse_intent('{"intent": "statement", "reply": "테니스 좋아하시는군요!"}') == "테니스 좋아하시는군요!"
    assert parse_intent('설명 {"intent":"statement","reply":"네"} 끝') == "네"
    assert parse_intent('{"intent": "request"}') is None
    assert parse_intent('{"intent": "statement", "reply": ""}') is None  # 반응문이 없으면 에이전트에 맡긴다
    assert parse_intent("not json") is None
    assert parse_intent("") is None
    assert parse_intent("[1]") is None


def test_gate_only_with_history_short_message_and_not_headless():
    assert should_gate("나는 테니스를 좋아해", H, headless=False)
    assert not should_gate("나는 테니스를 좋아해", [], headless=False)  # 첫 메시지
    assert not should_gate("나는 테니스를 좋아해", H, headless=True)  # 예약 실행
    assert not should_gate("가" * (GATE_MAX_CHARS + 1), H, headless=False)
    assert not should_gate("   ", H, headless=False)


def test_context_uses_recent_turns_only():
    hist = [HumanMessage(content=f"q{i}") if i % 2 == 0 else AIMessage(content=f"a{i}") for i in range(10)]
    ctx = _context(hist)
    assert "q6" in ctx and "a9" in ctx and "q0" not in ctx and ctx.count("\n") == 3


def test_prior_history_drops_the_current_message():
    from app.agent.intent import prior_history

    cur = H + [HumanMessage(content="나는 테니스를 좋아해")]
    assert prior_history(cur, "나는 테니스를 좋아해") == H
    assert prior_history(H, "다른 메시지") == H
    assert prior_history([HumanMessage(content="첫 메시지")], "첫 메시지") == []

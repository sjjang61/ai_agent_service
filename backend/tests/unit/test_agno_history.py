import asyncio
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.agno_engine import stream_team


class FakeTeam:
    """arun 에 전달된 인자와 additional_input 을 기록하는 가짜 Team (비스트리밍 경로)."""

    additional_input = None

    async def arun(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(member_responses=[], tools=[], content="ok", status=None, metrics=None)


def run(history, user_input):
    team = FakeTeam()

    async def go():
        return [e async for e in stream_team(team, user_input, history, "c1", "u1", streaming=False)]

    return team, asyncio.run(go())


def test_history_goes_to_additional_input_as_real_turns_and_input_is_current_message_only():
    history = [HumanMessage(content="나는 어디에 살아"), AIMessage(content="서울에 살고 계세요."), HumanMessage(content="지금 몇 시야?")]
    team, events = run(history, "지금 몇 시야?")
    # 현재 메시지는 history 에서 떼어 중복되지 않는다
    assert [(m.role, m.content) for m in team.additional_input] == [("user", "나는 어디에 살아"), ("assistant", "서울에 살고 계세요.")]
    assert isinstance(team.kwargs["input"], str) and team.kwargs["input"].startswith("지금 몇 시야?")
    assert events == [{"type": "token", "content": "ok"}]


def test_first_message_has_no_history_and_no_reminder():
    team, _ = run([HumanMessage(content="안녕")], "안녕")
    assert team.additional_input is None
    assert team.kwargs["input"] == "안녕"

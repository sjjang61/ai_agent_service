import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.agent import agno_engine


class _Team:
    """Agno Team 흉내: 토큰 이벤트와 완료 이벤트를 낸다."""

    async def arun(self, **kwargs):
        yield SimpleNamespace(event="TeamModelRequestCompleted", input_tokens=10, output_tokens=2, tool=None)
        yield SimpleNamespace(event="TeamRunContent", content="답", tool=None)
        yield SimpleNamespace(event="TeamRunCompleted", metrics=SimpleNamespace(input_tokens=10, output_tokens=2), tool=None)


def test_usage_is_recorded_even_if_consumer_stops_after_usage_event():
    saved = []

    async def fake_record(**kw):
        await asyncio.sleep(0.05)
        saved.append(kw)

    async def go():
        gen = agno_engine.stream_team(_Team(), "질문", [], "conv-1", "user-1", True, db=object(), llm_provider="openai", model="m")
        async for ev in gen:
            if ev["type"] == "usage":
                assert (ev["input_tokens"], ev["output_tokens"], ev["requests"]) == (10, 2, 1)
                break                      # 소비자가 먼저 끊긴다
        await gen.aclose()
        await asyncio.sleep(0.3)           # 독립 태스크가 끝날 시간

    with patch("app.services.token_usage_service.TokenUsageService.record_usage_detached", staticmethod(fake_record)):
        asyncio.run(go())
    assert saved and saved[0]["input_tokens"] == 10 and saved[0]["conversation_id"] == "conv-1"


def test_record_usage_detached_swallows_errors(monkeypatch):
    from app.services.token_usage_service import TokenUsageService

    async def boom(**kw):
        raise asyncio.CancelledError() if False else RuntimeError("db gone")

    monkeypatch.setattr(TokenUsageService, "record_usage", staticmethod(lambda db, **kw: boom()))
    asyncio.run(TokenUsageService.record_usage_detached(user_id="u", conversation_id="c", llm_provider="p", model_name="m", input_tokens=1, output_tokens=1))

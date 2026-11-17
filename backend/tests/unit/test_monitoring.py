"""에이전트 응답 모니터링: 도구 선택(none|opik|langfuse), 설정 실패가 서버를 막지 않는지, 스트림 병합."""
import asyncio

import pytest

from app.agent import side_events
from app.config import Settings, normalize_monitoring_type
from app.core import monitoring
from app.core.monitoring import backends


def S(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_monitoring_type_aliases_and_default():
    assert S().AGENT_MONITORING_TYPE == "none"  # 기본은 꺼짐
    assert S(AGENT_MONITORING_TYPE="opic").AGENT_MONITORING_TYPE == "opik"  # 오타·별칭
    assert S(AGENT_MONITORING_TYPE="OPIK").AGENT_MONITORING_TYPE == "opik"
    assert S(AGENT_MONITORING_TYPE="Langfuse").AGENT_MONITORING_TYPE == "langfuse"
    assert normalize_monitoring_type("off") == "none" and normalize_monitoring_type("") == "none"


def test_opik_target_self_hosted_and_cloud():
    t = backends.opik(S(OPIK_URL="http://localhost:15174/", OPIK_PROJECT_NAME="proj"))
    assert t.endpoint == "http://localhost:15174/api/v1/private/otel/v1/traces"
    assert t.headers == {"projectName": "proj"}  # 자체 호스팅은 인증 헤더가 없다
    c = backends.opik(S(OPIK_URL="https://www.comet.com/opik", OPIK_API_KEY="k", OPIK_WORKSPACE="ws"))
    assert c.endpoint == "https://www.comet.com/opik/api/v1/private/otel/v1/traces"
    assert c.headers["Authorization"] == "k" and c.headers["Comet-Workspace"] == "ws"


def test_langfuse_target_needs_keys_and_uses_basic_auth():
    with pytest.raises(backends.MonitoringConfigError):
        backends.langfuse(S(LANGFUSE_HOST="http://lf:3000"))
    t = backends.langfuse(S(LANGFUSE_HOST="http://lf:3000", LANGFUSE_PUBLIC_KEY="pk", LANGFUSE_SECRET_KEY="sk"))
    assert t.endpoint == "http://lf:3000/api/public/otel/v1/traces"
    assert t.headers["Authorization"] == "Basic cGs6c2s="  # base64("pk:sk")
    assert set(backends.BACKENDS) == {"opik", "langfuse"}


def test_setup_never_raises_and_stays_off_when_misconfigured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(monitoring, "_provider", None)
    monkeypatch.setattr(settings, "AGENT_MONITORING_TYPE", "none")
    assert monitoring.setup_monitoring() is None and not monitoring.is_enabled()
    monkeypatch.setattr(settings, "AGENT_MONITORING_TYPE", "langfuse")  # 키가 없다
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    assert monitoring.setup_monitoring() is None and not monitoring.is_enabled()  # 예외 없이 꺼진 채로 동작
    monkeypatch.setattr(settings, "AGENT_MONITORING_TYPE", "bogus")
    assert monitoring.setup_monitoring() is None
    monitoring.shutdown_monitoring()  # 꺼져 있을 때 호출해도 안전


def test_context_is_a_noop_when_disabled():
    with monitoring.monitoring_context(session_id="c", user_id="u", engine="agno"):
        pass  # 꺼져 있으면 아무 일도 하지 않는다


@pytest.mark.asyncio
async def test_merge_stream_runs_the_stream_in_one_task_and_propagates_errors():
    import contextvars

    var = contextvars.ContextVar("v", default="")
    q = side_events.open_channel("m1")
    tasks = set()

    async def gen():
        tasks.add(asyncio.current_task())
        var.set("set-in-gen")  # 한 태스크 안에서 시작한 컨텍스트(트레이스 스팬 등)는 다음 걸음에도 이어져야 한다
        yield "a"
        await asyncio.sleep(0.02)
        assert var.get() == "set-in-gen"
        tasks.add(asyncio.current_task())
        yield "b"

    got = [k async for k, _ in side_events.merge_stream(gen(), q)]
    assert got == ["team", "team"] and len(tasks) == 1  # 한 걸음마다 새 태스크를 만들지 않는다

    async def boom():
        yield "a"
        raise RuntimeError("model failed")

    with pytest.raises(RuntimeError, match="model failed"):
        [x async for x in side_events.merge_stream(boom(), q)]  # 실행 오류는 소비자에게 그대로 올라간다
    side_events.close_channel("m1", q)


@pytest.mark.asyncio
async def test_run_with_side_applies_context_inside_the_run_task():
    import contextvars

    var = contextvars.ContextVar("v2", default="")
    q = side_events.open_channel("m2")
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        t = var.set("in-ctx")
        try:
            yield
        finally:
            var.reset(t)

    async def work():
        return var.get()

    res = [p async for k, p in side_events.run_with_side(work(), q, ctx) if k == "done"]
    side_events.close_channel("m2", q)
    assert res == ["in-ctx"] and var.get() == ""


def test_opik_maps_openinference_session_and_user_to_thread_and_metadata():
    t = backends.opik(S())
    pairs = dict((dst, src) for src, dst in t.attr_map)
    assert pairs["thread_id"] == "session.id" and "opik.metadata.user_id" in pairs  # Opik 은 session.id 를 모르므로 옮겨 준다
    assert backends.langfuse(S(LANGFUSE_PUBLIC_KEY="a", LANGFUSE_SECRET_KEY="b")).attr_map == ()  # Langfuse 는 그대로 이해한다


def test_attr_mapper_copies_attributes_on_span_start():
    from opentelemetry.sdk.trace import TracerProvider

    mapper = monitoring._attr_mapper((("session.id", "thread_id"),))
    provider = TracerProvider()
    provider.add_span_processor(mapper)
    tracer = provider.get_tracer("t")
    with tracer.start_as_current_span("root", attributes={"session.id": "conv-1"}) as span:
        assert span.attributes["thread_id"] == "conv-1"
    with tracer.start_as_current_span("no-session") as span2:
        assert "thread_id" not in span2.attributes

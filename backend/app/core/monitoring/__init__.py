"""에이전트 응답 모니터링 (트레이스·지연·토큰·오류). AGENT_MONITORING_TYPE 으로 도구를 고른다 (none | opik | langfuse).

Agno 의 팀·에이전트·모델·도구 호출은 OpenInference 계측기로, LangChain 직접 호출은 LangChain 계측기로 자동 기록하고,
OpenTelemetry(OTLP/HTTP)로 선택한 도구에 보낸다. 어떤 경우에도 대화를 막지 않는다: 설정이 틀리거나 서버가 죽어 있으면 로그만 남기고 끈 채로 동작한다.
"""
import logging
from contextlib import contextmanager, nullcontext
from typing import Iterator, Optional

from app.config import settings
from app.core.monitoring.backends import BACKENDS, MonitoringConfigError, OtlpTarget

logger = logging.getLogger(__name__)

def _attr_mapper(pairs):
    """스팬이 시작될 때 속성을 복사하는 프로세서 (도구마다 대화·사용자 속성 이름이 다르다)."""
    from opentelemetry.sdk.trace import SpanProcessor

    class AttrMapper(SpanProcessor):
        def on_start(self, span, parent_context=None):  # noqa: ANN001
            attrs = span.attributes or {}
            for src, dst in pairs:
                v = attrs.get(src)
                if v not in (None, ""):
                    span.set_attribute(dst, v)

    return AttrMapper()


_provider = None  # 켜져 있을 때의 TracerProvider
_active: Optional[OtlpTarget] = None


def is_enabled() -> bool:
    return _provider is not None


def active_backend() -> Optional[str]:
    return _active.name if _active else None


def setup_monitoring() -> Optional[str]:
    """설정에 따라 모니터링을 켠다. 켜졌으면 도구 이름을, 꺼져 있거나 실패하면 None 을 돌려준다 (예외를 내지 않는다)."""
    global _provider, _active
    kind = settings.AGENT_MONITORING_TYPE
    if kind == "none" or _provider is not None:
        return active_backend()
    try:
        builder = BACKENDS.get(kind)
        if builder is None:
            raise MonitoringConfigError(f"지원하지 않는 AGENT_MONITORING_TYPE: {kind} (none | {' | '.join(BACKENDS)})")
        target = builder(settings)

        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import SpanLimits, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        rate = min(1.0, max(0.0, settings.MONITORING_SAMPLE_RATE))
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.MONITORING_SERVICE_NAME, "deployment.environment": settings.APP_ENV}),
            sampler=ParentBased(TraceIdRatioBased(rate)),
            # 기본 128개면 긴 대화(메시지마다 속성이 붙음)에서 '오래된 속성부터 버려' 입력 앞부분이 잘린다
            span_limits=SpanLimits(max_span_attributes=settings.MONITORING_MAX_SPAN_ATTRIBUTES),
        )
        if target.attr_map:
            provider.add_span_processor(_attr_mapper(target.attr_map))
        # 배치로 비동기 전송: 서버가 느리거나 죽어 있어도 대화 응답 경로를 막지 않는다
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=target.endpoint, headers=target.headers, timeout=10)))
        trace.set_tracer_provider(provider)

        from openinference.instrumentation.agno import AgnoInstrumentor

        AgnoInstrumentor().instrument(tracer_provider=provider)
        if settings.MONITORING_LANGCHAIN:
            from openinference.instrumentation.langchain import LangChainInstrumentor

            LangChainInstrumentor().instrument(tracer_provider=provider)
        _provider, _active = provider, target
        logger.info("[monitoring] %s 로 트레이스를 보냅니다 (%s, 표본 %.0f%%)", target.name, target.ui_url, rate * 100)
        return target.name
    except Exception as e:  # noqa: BLE001
        logger.warning("[monitoring] 켜지 못했습니다 (모니터링 없이 동작합니다): %s", e)
        return None


def shutdown_monitoring() -> None:
    """남은 트레이스를 서버에 보내고 끈다 (서버 종료 시)."""
    global _provider, _active
    if _provider is None:
        return
    try:
        _provider.force_flush(5000)
        _provider.shutdown()
    except Exception:  # noqa: BLE001
        logger.debug("[monitoring] 종료 중 오류", exc_info=True)
    _provider, _active = None, None


@contextmanager
def monitoring_context(session_id: str = "", user_id: str = "", **metadata) -> Iterator[None]:
    """이 안에서 일어나는 모든 에이전트·모델·도구 스팬에 대화(session)와 사용자 id 를 붙인다. 꺼져 있으면 아무 일도 하지 않는다."""
    if not is_enabled():
        with nullcontext():
            yield
        return
    try:
        from openinference.instrumentation import using_attributes

        cm = using_attributes(session_id=session_id or None, user_id=user_id or None, metadata={k: v for k, v in metadata.items() if v is not None} or None)
    except Exception:  # noqa: BLE001
        cm = nullcontext()
    with cm:
        yield

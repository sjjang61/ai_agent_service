"""모니터링 도구별 OTLP 내보내기 설정. 도구를 추가하려면 함수 하나를 만들어 BACKENDS 에 등록한다.

모든 도구가 OpenTelemetry(OTLP/HTTP)를 받으므로 계측 코드는 같고, 여기서는 '어디로(endpoint)·어떤 헤더로' 보낼지만 정한다.
"""
import base64
from dataclasses import dataclass
from typing import Callable

from app.config import Settings


@dataclass(frozen=True)
class OtlpTarget:
    name: str
    endpoint: str  # 트레이스 수신 전체 주소 (…/v1/traces)
    headers: dict[str, str]
    ui_url: str  # 사람이 보는 화면 주소 (로그·안내용)
    # 스팬에 이미 붙은 OpenInference 속성을 이 도구가 이해하는 속성으로도 복사한다 {원래 이름: 도구가 읽는 이름}
    attr_map: tuple[tuple[str, str], ...] = ()


class MonitoringConfigError(ValueError):
    """설정이 부족해 모니터링을 켤 수 없다 (메시지는 그대로 로그에 남긴다)"""


def opik(s: Settings) -> OtlpTarget:
    base = s.OPIK_URL.rstrip("/")
    headers = {"projectName": s.OPIK_PROJECT_NAME}
    if s.OPIK_API_KEY:  # Opik Cloud / 엔터프라이즈
        headers["Authorization"] = s.OPIK_API_KEY
        headers["Comet-Workspace"] = s.OPIK_WORKSPACE
    # 자체 호스팅: {OPIK_URL}/api/v1/private/otel, Cloud: https://www.comet.com/opik/api/v1/private/otel
    api = f"{base}/api/v1/private/otel"
    # Opik 은 session.id / user.id 를 모른다: 대화(thread)와 메타데이터로 보이게 옮긴다
    attr_map = (("session.id", "thread_id"), ("user.id", "opik.metadata.user_id"), ("session.id", "opik.metadata.conversation_id"))
    return OtlpTarget("opik", f"{api}/v1/traces", headers, base, attr_map)


def langfuse(s: Settings) -> OtlpTarget:
    if not (s.LANGFUSE_PUBLIC_KEY and s.LANGFUSE_SECRET_KEY):
        raise MonitoringConfigError("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY 가 필요합니다")
    base = s.LANGFUSE_HOST.rstrip("/")
    token = base64.b64encode(f"{s.LANGFUSE_PUBLIC_KEY}:{s.LANGFUSE_SECRET_KEY}".encode()).decode()
    return OtlpTarget("langfuse", f"{base}/api/public/otel/v1/traces", {"Authorization": f"Basic {token}"}, base)


BACKENDS: dict[str, Callable[[Settings], OtlpTarget]] = {"opik": opik, "langfuse": langfuse}

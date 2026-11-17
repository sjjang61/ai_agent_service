"""브라우저 에이전트 안전 정책: 어떤 동작을 자동으로 실행하고, 어떤 동작은 사용자 승인을 받을지 판정한다.

원칙
  - 읽기 동작(이동, 스냅샷, 스크롤, 뒤로, 대기, 스크린샷)은 자동.
  - 위험 신호가 없는 쓰기 동작(검색 제출, 일반 버튼 클릭, Enter)도 자동. 승인(ASK)은 대상을 알 수 없는 클릭과 주문·결제 주소의 Enter 뿐이고,
    같은 대화에서 같은 도메인은 한 번 승인하면 재승인을 생략한다.
  - 결제·주문·장바구니·삭제·전송 같은 라벨이거나 금융·결제 도메인, 비밀번호 입력이면 재승인 생략 없이 매번 승인(ASK_ALWAYS).
  - 차단 도메인(BROWSER_BLOCKED_DOMAINS)은 이동 자체를 거부, 허용 목록(BROWSER_ALLOWED_DOMAINS)이 있으면 그 밖의 도메인도 거부.
순수 함수로만 구성해 테스트하기 쉽게 한다.
"""
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from app.config import settings

AUTO, ASK, ASK_ALWAYS = "auto", "ask", "ask_always"

READ_ACTIONS = {"goto", "snapshot", "scroll", "back", "screenshot", "wait", "reload", "ping"}

# 되돌리기 어려운 동작을 암시하는 라벨 (한/영)
RISKY_LABEL = re.compile(
    r"결제|구매|주문|장바구니|담기|바로\s*구매|add to (cart|bag|basket)|cart\b|basket\b|예약\s*확정|삭제|탈퇴|해지|취소하기|송금|이체|입금|전송|보내기|발송|게시|등록하기|제출|비밀번호|"
    r"pay\b|payment|purchase|buy\b|order\b|checkout|place order|delete|remove|deactivate|cancel (my )?(account|subscription)|"
    r"transfer|withdraw|send\b|publish|post\b|submit|confirm|password|unsubscribe",
    re.I,
)
# 이 주소 경로에서의 Enter·제출은 주문/결제 단계일 수 있어 확인한다
RISKY_PATH = re.compile(r"checkout|/order|payment|/pay\b|/cart|basket|결제|주문|장바구니", re.I)

_SENSITIVE_TOKENS = {
    "paypal", "stripe", "checkout", "toss", "tosspayments", "kakaopay", "naverpay", "payco", "pay", "payment", "payments",
    "wallet", "venmo", "alipay",
}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _matches(host: str, rule: str) -> bool:
    rule = rule.strip().lower().removeprefix("www.")
    return bool(rule) and (host == rule or host.endswith("." + rule))


def host_of(url: str) -> str:
    return _host(url)


def is_sensitive_host(host: str) -> bool:
    """금융·결제 계열 도메인으로 보이는지 (항상 승인 대상)."""
    for rule in settings.BROWSER_SENSITIVE_DOMAINS:
        if _matches(host, rule):
            return True
    tokens = re.split(r"[.\-]", host)
    return any(t in _SENSITIVE_TOKENS or "bank" in t or "securities" in t for t in tokens)


def domain_denied(url: str) -> Optional[str]:
    """이동할 수 없는 도메인이면 사유, 아니면 None."""
    host = _host(url)
    if not host:
        return None
    for rule in settings.BROWSER_BLOCKED_DOMAINS:
        if _matches(host, rule):
            return f"차단된 도메인입니다: {host}"
    allowed = settings.BROWSER_ALLOWED_DOMAINS
    if allowed and not any(_matches(host, r) for r in allowed):
        return f"허용 목록에 없는 도메인입니다: {host}"
    return None


@dataclass
class Decision:
    level: str  # AUTO | ASK | ASK_ALWAYS
    reason: str = ""
    label: str = ""


def _element(elements: list[dict], ref: Optional[int]) -> Optional[dict]:
    for e in elements or []:
        if e.get("ref") == ref:
            return e
    return None


def classify(payload: dict, elements: list[dict], url: str) -> Decision:
    """브라우저 명령 하나의 승인 필요 수준. elements 는 가장 최근 snapshot 의 요소 목록, url 은 현재 주소."""
    action = payload.get("cmd") or payload.get("action") or ""
    host = _host(url)
    sensitive = is_sensitive_host(host) if host else False

    if action in READ_ACTIONS:
        return Decision(AUTO)

    if action == "select":
        return Decision(AUTO)  # 값만 고르는 동작. 제출은 별도 동작이다

    if action == "type":
        el = _element(elements, payload.get("ref"))
        label = (el or {}).get("label", "") or (el or {}).get("placeholder", "") or (el or {}).get("name", "")
        is_password = (el or {}).get("type") == "password"
        if payload.get("submit"):
            if sensitive or is_password or RISKY_LABEL.search(label):
                return Decision(ASK_ALWAYS, "입력한 내용을 제출합니다", label)
            return Decision(AUTO)  # 위험 신호가 없는 입력 제출(검색·필터 등)은 자동
        if is_password and sensitive:
            return Decision(ASK_ALWAYS, "금융·결제 사이트의 비밀번호 입력란에 입력합니다", label)
        return Decision(AUTO)

    if action == "press":
        key = str(payload.get("key") or "Enter")
        if key.lower() in ("enter", "return"):
            if sensitive:
                return Decision(ASK_ALWAYS, "Enter 키로 제출할 수 있습니다", "Enter")
            if RISKY_PATH.search(urlparse(url).path or ""):
                return Decision(ASK, "주문·결제 단계에서의 Enter 입니다", "Enter")
            return Decision(AUTO)
        return Decision(AUTO)

    if action == "click":
        el = _element(elements, payload.get("ref"))
        if el is None:
            return Decision(ASK, "대상 요소를 확인할 수 없는 클릭입니다", "")
        label = (el.get("label") or el.get("value") or el.get("name") or "").strip()
        tag, typ, role = el.get("tag", ""), el.get("type", ""), el.get("role", "")
        if tag == "a" or role == "link":
            return Decision(AUTO)  # 링크는 이동일 뿐이다. 라벨은 검색 결과 제목·주소 같은 본문이라 위험 단어(order 등)가 섞여 있어도 판단 근거가 되지 않는다
        if RISKY_LABEL.search(label[:40]):  # 버튼 라벨은 짧다. 긴 문구는 설명문이므로 앞부분만 본다
            return Decision(ASK_ALWAYS, "되돌리기 어려운 동작일 수 있습니다", label)
        if sensitive:
            if tag == "button" or typ in ("submit", "button", "image") or role == "button":
                return Decision(ASK_ALWAYS, "금융·결제 사이트에서의 클릭입니다", label)
        return Decision(AUTO)  # 위험 신호(라벨·금융 도메인)가 없는 클릭은 자동  # 링크·탭·체크박스·메뉴 등 단순 이동/토글

    return Decision(ASK, "알 수 없는 동작입니다", "")


class ApprovalMemory:
    """대화별로 승인된 도메인을 기억한다 (ASK 수준에서만 재승인 생략). 프로세스 메모리 기준이며 대화가 끝나면 비워도 된다."""

    _approved: dict[str, set[str]] = {}

    @classmethod
    def is_approved(cls, conversation_id: str, host: str) -> bool:
        return bool(conversation_id) and host in cls._approved.get(conversation_id, set())

    @classmethod
    def remember(cls, conversation_id: str, host: str) -> None:
        if conversation_id and host:
            cls._approved.setdefault(conversation_id, set()).add(host)
            if len(cls._approved) > 500:  # 오래된 대화부터 정리
                cls._approved.pop(next(iter(cls._approved)))

    @classmethod
    def forget(cls, conversation_id: str) -> None:
        cls._approved.pop(conversation_id, None)


def needs_approval(decision: Decision, conversation_id: str, url: str) -> bool:
    if decision.level == AUTO:
        return False
    if decision.level == ASK and ApprovalMemory.is_approved(conversation_id, _host(url)):
        return False
    return True


# ── 프롬프트 인젝션 방어: 웹 페이지 내용을 '신뢰할 수 없는 데이터'로 감싸서 모델에 전달한다 ──
_FENCE = "<<<WEB_CONTENT>>>"
_FENCE_END = "<<<END_WEB_CONTENT>>>"


def fence_untrusted(text: str) -> str:
    """페이지 텍스트를 데이터 구역으로 감싼다. 본문에 같은 구분자가 있으면 무력화해 구역을 벗어나지 못하게 한다."""
    safe = text.replace("<<<", "‹‹‹").replace(">>>", "›››")
    return f"{_FENCE}\n{safe}\n{_FENCE_END}"

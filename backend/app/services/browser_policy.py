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

# 결제를 확정하는 동작의 라벨·주소. 승인(ASK_ALWAYS)과 달리 사용자가 승인해도 실행하지 않는다: 이 에이전트는 결제 직전까지만 진행하고 멈춘다.
PAYMENT_LABEL = re.compile(
    r"결제\s*하기|결제\s*진행|결제\s*하러|지금\s*결제|바로\s*결제|최종\s*결제|결제\s*완료|결제\s*요청|\d[\d,]*\s*원\s*결제|무통장\s*입금\s*(신청|하기)|"
    r"pay\s*now|pay\s*(and|&)\s*(book|reserve|order)|place\s*(your\s*)?order|complete\s*(my\s*)?(purchase|order|payment|booking)|"
    r"confirm\s*(and\s*)?(pay|purchase|booking)|book\s*(now\s*)?(and|&)\s*pay",
    re.I,
)
PAYMENT_URL = re.compile(r"/(payments?|pay|checkout/(pay|payment)|order/pay|pay[-_]?(sheet|process|complete))(/|$)", re.I)
MAX_BUTTON_LABEL = 30  # 이보다 긴 문구는 설명문이라 버튼 라벨로 보지 않는다


def payment_stop(payload: dict, elements: list[dict], url: str, words: tuple = (), url_words: tuple = ()) -> Optional[str]:
    """결제·주문 확정으로 이어지는 동작이면 에이전트에게 돌려줄 중단 안내를, 아니면 None.
    words/url_words 는 분야(쇼핑·영화·항공·호텔)가 더하는 '누르지 않을 라벨'과 '이동하지 않을 주소 문구'."""
    if not settings.BROWSER_BLOCK_PAYMENT:
        return None
    action = payload.get("cmd") or payload.get("action") or ""
    target = ""
    if action == "goto":
        target_url = str(payload.get("url") or "")
        path = urlparse(target_url).path or ""
        if PAYMENT_URL.search(path) or any(w and w in target_url.lower() for w in url_words):
            target = target_url[:120]
    elif action == "click":
        el = _element(elements, payload.get("ref"))
        label = ((el or {}).get("label") or (el or {}).get("value") or (el or {}).get("name") or "").strip()
        if label and len(label) <= MAX_BUTTON_LABEL and (PAYMENT_LABEL.search(label) or any(w and w in label.lower() for w in words)):
            target = label
    elif action == "press" and str(payload.get("key") or "Enter").lower() in ("enter", "return") or (action == "type" and payload.get("submit")):
        if PAYMENT_URL.search(urlparse(url).path or "") or any(w and w in (url or "").lower() for w in url_words):
            target = "결제 화면에서의 제출"
    if not target:
        return None
    return (f"[결제 직전] “{target}” 은(는) 결제·주문 확정으로 이어지는 동작이라 실행하지 않았습니다. 이 에이전트는 결제 직전까지만 진행합니다. "
            "우회하거나 다른 방법으로 결제하지 마세요. 지금까지 확인한 내용(상품·가격·옵션·선택한 항목)과 현재 화면 주소를 최종 보고하고 멈추세요. 결제는 사용자가 직접 진행합니다.")


# 페이지 confirm 대화상자 중 '조회를 계속하려면 안내를 확인했다는 동의'만 확인으로 응답한다 (KOBUS 조회하기: "취소수수료 내용에 동의하십니까?").
# 결제·구매·삭제·탈퇴·신청처럼 상태를 바꾸는 말이 함께 있으면 허용하지 않는다. 그 밖의 confirm 은 계속 취소한다.
_DIALOG_OK = re.compile(r"(취소\s*)?수수료[^\n]{0,20}(내용|안내|규정)[^\n]{0,20}동의|(이용|유의|안내|운행)\s*(안내|사항|시간)[^\n]{0,20}(확인|동의)하(십니까|시겠습니까)")
_DIALOG_DENY = re.compile(r"결제|구매|삭제|탈퇴|주문|송금|이체|신청|예약을 (확정|진행)|예매를 (확정|진행)|취소하시겠|환불하시겠|로그아웃")


def dialog_confirm_ok(message: str) -> bool:
    """이 confirm 대화상자를 '확인'으로 응답해도 되는가 (조회 단계의 안내 동의만)."""
    msg = message or ""
    return bool(_DIALOG_OK.search(msg)) and not _DIALOG_DENY.search(msg)


def confirm_hit(payload: dict, elements: list[dict], words: tuple = ()) -> Optional[str]:
    """누르려는 버튼이 분야의 '승인 후 누를 문구'(예약·동의 확정)에 해당하면 그 라벨을, 아니면 None.
    '문구@조건' 은 현재 화면에 조건 문구가 들어 있는 요소가 함께 있을 때만 적용한다 (같은 '예약하기' 라벨이 패널을 여는 버튼일 때와 확정 버튼일 때를 구분한다)."""
    if not words or (payload.get("cmd") or payload.get("action") or "") != "click":
        return None
    el = _element(elements, payload.get("ref"))
    label = ((el or {}).get("label") or (el or {}).get("value") or (el or {}).get("name") or "").strip()
    if not label or len(label) > MAX_BUTTON_LABEL:
        return None
    low = label.lower()
    for w in words:
        word, _, cond = str(w).partition("@")
        word, cond = word.strip().lower(), cond.strip().lower()
        if word and word in low and (not cond or any(cond in str(e.get("label") or "").lower() for e in elements or [])):
            return label
    return None


def confirm_stop(label: str) -> str:
    """사이트 분석·검증에서 '승인 후 누를 문구' 버튼을 눌러 보려 할 때의 중단 안내 (결제 직전 안내와 같은 접두사를 써서 일괄 동작도 멈춘다)."""
    return (f"[결제 직전] “{label}” 은(는) 예약·동의를 확정하는 동작이라 사이트 분석·검증에서는 실행하지 않았습니다. 이 단계 이전까지 확인한 내용과 현재 화면 주소를 보고하고 멈추세요. "
            "우회하거나 다른 방법으로 확정하지 마세요.")


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


def classify(payload: dict, elements: list[dict], url: str, confirm_label: Optional[str] = None) -> Decision:
    """브라우저 명령 하나의 승인 필요 수준. elements 는 가장 최근 snapshot 의 요소 목록, url 은 현재 주소."""
    action = payload.get("cmd") or payload.get("action") or ""
    host = _host(url)
    sensitive = is_sensitive_host(host) if host else False

    if action in READ_ACTIONS:
        return Decision(AUTO)

    if action == "click" and confirm_label:  # 분야가 정한 '승인 후 누를 문구'(예약·동의 확정): 사용자 작업에서도 매번 승인을 받는다
        return Decision(ASK_ALWAYS, "예약·동의를 확정하는 동작입니다", confirm_label)

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

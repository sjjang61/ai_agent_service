"""비공개 앱의 소유자 인증: 실행 티켓(일회용, 60초)과 세션 쿠키 값. 메인 앱(로그인한 소유자)이 발급하고 게이트웨이가 검증한다.

앱은 메인 앱과 origin 이 달라 로그인 정보를 알 수 없으므로, 메인 앱이 서명한 티켓을 URL 로 넘기고 게이트웨이가 그것을 세션 쿠키로 바꾼다.
서명은 SECRET_KEY 의 HMAC-SHA256 이다. 앱의 session_epoch 를 올리면 이미 발급된 세션이 모두 무효가 된다.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from app.config import settings

TICKET_TTL = 60
SESSION_TTL = 8 * 3600
_used: dict[str, float] = {}  # 사용한 티켓 jti → 만료 시각 (일회용 보장. 단일 프로세스 전제)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: dict) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(mac)}"


def _verify(token: Optional[str], kind: str) -> Optional[dict]:
    if not token or "." not in token:
        return None
    body, _, mac = token.partition(".")
    try:
        want = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(want, _unb64(mac)):
            return None
        p = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(p, dict) or p.get("k") != kind or p.get("exp", 0) < time.time():
        return None
    return p


def make_ticket(app_id: str, user_id: str) -> str:
    return _sign({"k": "ticket", "aid": app_id, "uid": user_id, "jti": secrets.token_hex(8), "exp": time.time() + TICKET_TTL})


def make_session(app_id: str, user_id: str, epoch: int) -> str:
    return _sign({"k": "session", "aid": app_id, "uid": user_id, "ep": epoch, "exp": time.time() + SESSION_TTL})


def check_ticket(token: Optional[str], app_id: str, owner_id: str) -> bool:
    """서명·만료·앱·소유자가 맞고 아직 쓰지 않은 티켓이면 True (그리고 사용 처리)."""
    p = _verify(token, "ticket")
    if not p or p.get("aid") != app_id or p.get("uid") != owner_id:
        return False
    now = time.time()
    for j in [j for j, e in _used.items() if e < now]:
        del _used[j]
    if p["jti"] in _used:
        return False
    _used[p["jti"]] = p["exp"]
    return True


def make_review_ticket(app_id: str, reviewer_id: str) -> str:
    """검수자 미리보기용 일회용 티켓: 승인 전(공개되지 않은) 앱을 공개 호스트명으로 열어 볼 수 있다."""
    return _sign({"k": "rticket", "aid": app_id, "uid": reviewer_id, "jti": secrets.token_hex(8), "exp": time.time() + TICKET_TTL})


def check_review_ticket(token: Optional[str], app_id: str) -> bool:
    p = _verify(token, "rticket")
    if not p or p.get("aid") != app_id:
        return False
    now = time.time()
    for j in [j for j, e in _used.items() if e < now]:
        del _used[j]
    if p["jti"] in _used:
        return False
    _used[p["jti"]] = p["exp"]
    return True


def make_review_session(app_id: str) -> str:
    return _sign({"k": "rsession", "aid": app_id, "exp": time.time() + 3600})


def check_review_session(token: Optional[str], app_id: str) -> bool:
    p = _verify(token, "rsession")
    return bool(p and p.get("aid") == app_id)


def check_session(token: Optional[str], app_id: str, owner_id: str, epoch: int) -> bool:
    p = _verify(token, "session")
    return bool(p and p.get("aid") == app_id and p.get("uid") == owner_id and p.get("ep") == epoch)

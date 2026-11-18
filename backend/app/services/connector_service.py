"""커넥터 카탈로그와 Google OAuth 연결.

한 번 Google 계정으로 인증하면 계정(ConnectorAccount) 하나에 허용한 범위가 쌓이고, 커넥터(Gmail·Calendar·Drive·Docs·Sheets·Slides)는
그 범위 안에서 켜고 끈다. 새 커넥터를 켤 때는 이미 허용한 범위에 필요한 범위만 더해 다시 동의받는다(증분 인증).
"""
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import crypto
from app.models.connector_account import ConnectorAccount

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
STATE_TTL = 600  # 인증 화면에 머무를 수 있는 시간(초)

_G = "https://www.googleapis.com/auth/"
BASE_SCOPES = ["openid", "email"]

# 커넥터 카탈로그. scopes 는 그 커넥터가 하는 일에 필요한 최소 범위 (Gmail 은 조회만, Calendar 는 일정 생성·수정·삭제까지)
CONNECTORS: dict[str, dict] = {
    "gmail": {
        "name": "Gmail", "description": "메일·스레드 검색과 조회.", "category": "업무 문서",
        "scopes": [_G + "gmail.readonly"],
    },
    "google_calendar": {
        "name": "Google Calendar", "description": "캘린더·일정 조회와 일정 만들기·수정·삭제.", "category": "업무 문서",
        "scopes": [_G + "calendar.events", _G + "calendar.calendarlist.readonly"],
    },
    "google_drive": {
        "name": "Google Drive", "description": "드라이브 파일 검색과 내용 조회.", "category": "업무 문서",
        "scopes": [_G + "drive.readonly"],
    },
    "google_docs": {
        "name": "Google Docs", "description": "문서 검색과 본문 조회.", "category": "업무 문서",
        "scopes": [_G + "documents.readonly", _G + "drive.metadata.readonly"],
    },
    "google_sheets": {
        "name": "Google Sheets", "description": "스프레드시트 검색과 셀 조회.", "category": "업무 문서",
        "scopes": [_G + "spreadsheets.readonly", _G + "drive.metadata.readonly"],
    },
    "google_slides": {
        "name": "Google Slides", "description": "프레젠테이션 검색과 슬라이드 조회.", "category": "업무 문서",
        "scopes": [_G + "presentations.readonly", _G + "drive.metadata.readonly"],
    },
}


class ConnectorError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 연결 오류. expired=True 면 다시 연결해야 하는 오류(토큰 만료·취소)다."""

    def __init__(self, message: str = "", expired: bool = False):
        super().__init__(message)
        self.expired = expired


def redirect_uri() -> str:
    return settings.GOOGLE_OAUTH_REDIRECT_URI or f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/connectors/google/callback"


def configured() -> bool:
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


# ── 인증 상태(state) ───────────────────────────────────────────────────────
def make_state(user_id: str, connector_id: str) -> str:
    """콜백에서 '누가 어느 커넥터를 연결하는지'를 검증하는 서명된 값 (Fernet: 위·변조되면 복호화 실패, 만료 시각 포함)"""
    return crypto.encrypt(json.dumps({"u": user_id, "c": connector_id, "exp": int(time.time()) + STATE_TTL}))


def read_state(state: str) -> tuple[str, str]:
    try:
        data = json.loads(crypto.decrypt(state))
    except Exception as e:  # noqa: BLE001
        raise ConnectorError("인증 요청이 올바르지 않습니다. 다시 시도해 주세요.") from e
    if int(data.get("exp", 0)) < time.time():
        raise ConnectorError("인증 시간이 지났습니다. 다시 시도해 주세요.")
    return str(data["u"]), str(data["c"])


def needed_scopes(connector_id: str, granted: str = "") -> list[str]:
    """이미 허용한 범위에 이 커넥터의 범위를 더한 전체 (증분 인증에 쓴다)"""
    out = list(BASE_SCOPES)
    for s in [*granted.split(), *CONNECTORS[connector_id]["scopes"]]:
        if s and s not in out:
            out.append(s)
    return out


def build_auth_url(user_id: str, connector_id: str, granted: str = "") -> str:
    if not configured():
        raise ConnectorError("Google OAuth 설정이 없습니다. 서버의 GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET 을 설정하세요.")
    if connector_id not in CONNECTORS:
        raise ConnectorError("알 수 없는 커넥터입니다.")
    q = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(needed_scopes(connector_id, granted)),
        "access_type": "offline",  # refresh token 을 받아 계속 쓸 수 있게 한다
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": make_state(user_id, connector_id),
    }
    return f"{AUTH_URL}?{urlencode(q)}"


# ── 계정 저장·조회 ────────────────────────────────────────────────────────
class ConnectorService:
    @staticmethod
    async def account(user_id: str, db: AsyncSession) -> Optional[ConnectorAccount]:
        r = await db.execute(select(ConnectorAccount).where(ConnectorAccount.user_id == user_id, ConnectorAccount.provider == "google"))
        return r.scalar_one_or_none()

    @staticmethod
    async def enabled_ids(user_id: str, db: AsyncSession) -> list[str]:
        acc = await ConnectorService.account(user_id, db)
        return [c for c in (acc.connectors or []) if c in CONNECTORS] if acc else []

    @staticmethod
    async def complete_oauth(code: str, state: str, db: AsyncSession) -> tuple[str, str]:
        """콜백 처리: 코드를 토큰으로 바꿔 저장하고 커넥터를 켠다. (user_id, connector_id) 를 돌려준다."""
        user_id, connector_id = read_state(state)
        if connector_id not in CONNECTORS:
            raise ConnectorError("알 수 없는 커넥터입니다.")
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(TOKEN_URL, data={
                "code": code, "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": redirect_uri(), "grant_type": "authorization_code",
            })
            if r.status_code != 200:
                raise ConnectorError(f"Google 인증에 실패했습니다: {_err(r)}")
            tok = r.json()
            email = None
            try:
                ui = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {tok['access_token']}"})
                email = ui.json().get("email") if ui.status_code == 200 else None
            except Exception:  # noqa: BLE001
                pass
        granted = str(tok.get("scope") or "")
        missing = [s for s in CONNECTORS[connector_id]["scopes"] if s not in granted.split()]
        if missing:  # 동의 화면에서 일부 권한을 끈 경우
            raise ConnectorError("필요한 권한이 모두 허용되지 않았습니다. 다시 연결하면서 모든 항목을 허용해 주세요.")
        acc = await ConnectorService.account(user_id, db)
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=int(tok.get("expires_in", 3600)))
        if acc is None:
            acc = ConnectorAccount(user_id=user_id, provider="google", scopes=granted, connectors=[])
            db.add(acc)
        acc.scopes = " ".join(dict.fromkeys([*(acc.scopes or "").split(), *granted.split()]))
        acc.email = email or acc.email
        if tok.get("refresh_token"):
            acc.refresh_token_enc = crypto.encrypt(tok["refresh_token"])
        if not acc.refresh_token_enc:
            raise ConnectorError("Google 이 갱신 토큰을 주지 않았습니다. Google 계정의 '앱 액세스 권한'에서 이 앱을 제거한 뒤 다시 연결해 주세요.")
        acc.access_token_enc = crypto.encrypt(tok["access_token"])
        acc.expires_at = expires
        acc.connectors = list(dict.fromkeys([*(acc.connectors or []), connector_id]))
        await db.commit()
        return user_id, connector_id

    @staticmethod
    async def disconnect(user_id: str, connector_id: str, db: AsyncSession) -> None:
        """커넥터를 끈다. 켜진 커넥터가 하나도 없으면 Google 쪽 허용도 취소하고 계정 정보를 지운다."""
        acc = await ConnectorService.account(user_id, db)
        if acc is None:
            return
        acc.connectors = [c for c in (acc.connectors or []) if c != connector_id]
        if not acc.connectors:
            token = None
            try:
                token = crypto.decrypt(acc.refresh_token_enc) if acc.refresh_token_enc else None
            except ValueError:
                pass
            await db.delete(acc)
            await db.commit()
            if token:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(REVOKE_URL, data={"token": token})
                except Exception:  # noqa: BLE001
                    pass  # 취소 실패는 무시한다 (Google 계정의 '앱 액세스 권한'에서 직접 지울 수 있다)
        else:
            await db.commit()

    @staticmethod
    async def access_token(acc: ConnectorAccount, db: AsyncSession, force: bool = False) -> str:
        """유효한 access token. 만료됐으면 refresh token 으로 갱신해 저장한다."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if not force and acc.access_token_enc and acc.expires_at and acc.expires_at > now + timedelta(seconds=60):
            return crypto.decrypt(acc.access_token_enc)
        if not acc.refresh_token_enc:
            raise ConnectorError("Google 계정 연결이 끊어졌습니다. 커넥터 화면에서 다시 연결해 주세요.", expired=True)
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(TOKEN_URL, data={
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID, "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "refresh_token": crypto.decrypt(acc.refresh_token_enc), "grant_type": "refresh_token",
            })
        if r.status_code >= 500:  # Google 쪽 일시 장애: 연결이 끊어진 것이 아니다
            raise ConnectorError(f"Google 서버가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해 주세요. ({r.status_code})")
        if r.status_code != 200:
            raise ConnectorError(f"Google 계정 연결이 만료됐습니다. 커넥터 화면에서 다시 연결해 주세요. ({_err(r)})", expired=True)
        tok = r.json()
        acc.access_token_enc = crypto.encrypt(tok["access_token"])
        acc.expires_at = now + timedelta(seconds=int(tok.get("expires_in", 3600)))
        await db.commit()
        return tok["access_token"]

    @staticmethod
    async def verify(user_id: str, db: AsyncSession) -> dict:
        """저장된 연결이 지금도 쓸 수 있는지 Google 에 실제로 확인한다 (refresh token 으로 새 access token 을 받아 본다).
        status: valid(정상) | expired(다시 연결해야 함) | error(일시 오류 등 판단 보류) | none(연결 없음)."""
        acc = await ConnectorService.account(user_id, db)
        if not acc or not (acc.connectors or []):
            return {"status": "none", "message": "연결된 계정이 없습니다"}
        try:
            await ConnectorService.access_token(acc, db, force=True)
        except ConnectorError as e:
            return {"status": "expired" if e.expired else "error", "message": str(e), "account_email": acc.email}
        except httpx.HTTPError as e:
            return {"status": "error", "message": f"Google 에 연결하지 못했습니다 ({type(e).__name__})", "account_email": acc.email}
        return {"status": "valid", "message": "연결이 정상입니다", "account_email": acc.email}


def _err(r: httpx.Response) -> str:
    try:
        d = r.json()
        e = d.get("error")
        return str(d.get("error_description") or (e.get("message") if isinstance(e, dict) else e) or r.text)[:200]
    except Exception:  # noqa: BLE001
        return r.text[:200]

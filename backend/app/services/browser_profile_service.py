"""사용자 브라우저 프로필(로그인 상태) 저장소. storage_state 를 암호화해 DB 에 둔다."""
import json
import logging
from collections import Counter
from typing import Optional

from sqlalchemy import select

from app.core.crypto import decrypt, encrypt
from app.db.session import AsyncSessionLocal
from app.models.browser_profile import BrowserProfile

logger = logging.getLogger(__name__)

MAX_STATE_BYTES = 2 * 1024 * 1024  # 사용자당 프로필 상한
# 금융·결제 사이트의 세션은 저장하지 않는다 (유출 시 피해가 크다)
BLOCKED_DOMAINS = (
    "paypal.com", "stripe.com", "toss.im", "tosspayments.com", "kakaopay.com", "payco.com",
    "kbstar.com", "shinhan.com", "wooribank.com", "hanabank.com", "nonghyup.com", "ibk.co.kr",
)


def _site(domain: str) -> str:
    """쿠키 domain('.www.linkedin.com') → 사이트 단위('linkedin.com'). 한국형 2단계 TLD(co.kr 등)는 3단어로 자른다."""
    parts = domain.strip(".").lower().split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "or", "go", "ne", "ac", "com", "net", "org") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else ".".join(parts)


def _blocked(site: str) -> bool:
    return any(site == d or site.endswith("." + d) for d in BLOCKED_DOMAINS)


def sanitize_state(state: dict) -> dict:
    """차단 도메인 쿠키/스토리지 제거."""
    cookies = [c for c in state.get("cookies", []) if not _blocked(_site(str(c.get("domain", ""))))]
    origins = []
    for o in state.get("origins", []):
        host = str(o.get("origin", "")).split("://")[-1].split("/")[0].split(":")[0]
        if not _blocked(_site(host)):
            origins.append(o)
    return {"cookies": cookies, "origins": origins}


def summarize(state: dict) -> list[dict]:
    cnt = Counter(_site(str(c.get("domain", ""))) for c in state.get("cookies", []))
    return [{"domain": d, "cookies": n} for d, n in sorted(cnt.items())]


class BrowserProfileService:
    @staticmethod
    async def load_state(user_id: str) -> Optional[str]:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(BrowserProfile).where(BrowserProfile.user_id == user_id))).scalar_one_or_none()
            if not row:
                return None
            try:
                return decrypt(row.state_enc)
            except ValueError:
                logger.warning("[browser] 프로필 복호화 실패 user=%s", user_id)
                return None

    @staticmethod
    async def save_state(user_id: str, state: dict) -> list[dict]:
        """storage_state 를 저장하고 도메인 요약을 돌려준다. 쿠키가 하나도 없으면 프로필을 지운다."""
        state = sanitize_state(state)
        domains = summarize(state)
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(BrowserProfile).where(BrowserProfile.user_id == user_id))).scalar_one_or_none()
            if not state["cookies"] and not state["origins"]:
                if row:
                    await db.delete(row)
                    await db.commit()
                return []
            raw = json.dumps(state, ensure_ascii=False)
            if len(raw.encode()) > MAX_STATE_BYTES:
                raise ValueError("브라우저 프로필이 너무 큽니다 (2MB 초과). 일부 사이트의 로그인 상태를 삭제해 주세요")
            if row is None:
                row = BrowserProfile(user_id=user_id, state_enc="", domains=[], size_bytes=0)
                db.add(row)
            row.state_enc, row.domains, row.size_bytes = encrypt(raw), domains, len(raw)
            await db.commit()
        return domains

    @staticmethod
    async def info(user_id: str) -> dict:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(select(BrowserProfile).where(BrowserProfile.user_id == user_id))).scalar_one_or_none()
            if not row:
                return {"has_profile": False, "domains": [], "size_bytes": 0, "updated_at": None}
            return {"has_profile": True, "domains": row.domains or [], "size_bytes": row.size_bytes, "updated_at": row.updated_at}

    @staticmethod
    async def delete(user_id: str, domain: Optional[str] = None) -> bool:
        """domain 이 없으면 프로필 전체, 있으면 그 사이트의 쿠키·스토리지만 지운다."""
        raw = await BrowserProfileService.load_state(user_id)
        if raw is None:
            return False
        if not domain:
            async with AsyncSessionLocal() as db:
                row = (await db.execute(select(BrowserProfile).where(BrowserProfile.user_id == user_id))).scalar_one_or_none()
                if row:
                    await db.delete(row)
                    await db.commit()
            return True
        state = json.loads(raw)
        domain = domain.lower().strip(".")
        state["cookies"] = [c for c in state.get("cookies", []) if _site(str(c.get("domain", ""))) != domain]
        state["origins"] = [
            o for o in state.get("origins", [])
            if _site(str(o.get("origin", "")).split("://")[-1].split("/")[0].split(":")[0]) != domain
        ]
        await BrowserProfileService.save_state(user_id, state)
        return True

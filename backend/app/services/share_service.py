"""대화 공유: 스냅샷 만들기·링크 발급/해제·공개 조회"""
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation
from app.models.shared_conversation import SharedConversation
from app.services.chat_service import ChatService

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # DB 는 naive UTC 로 비교한다


def extract_widgets(steps) -> list:
    """create_widget 의 성공한 결과만 꺼낸다 (화면에 그리는 표·차트 데이터). 다른 도구 기록은 공유하지 않는다."""
    out = []
    for s in steps or []:
        if not isinstance(s, dict) or s.get("type") != "tool_result" or s.get("tool") != "create_widget" or not isinstance(s.get("output"), str):
            continue
        try:
            w = (json.loads(s["output"]) or {}).get("widget")
        except (ValueError, TypeError):
            continue
        if isinstance(w, dict) and w.get("type") and w.get("spec") is not None:
            out.append(w)
    return out


def build_snapshot(messages: list, limit: Optional[int] = None) -> list:
    limit = limit or settings.SHARE_MAX_MESSAGES
    rows = []
    for m in messages:
        if m.role not in ("user", "assistant") or not (m.content or "").strip():
            continue
        rows.append({
            "role": m.role,
            "content": m.content,
            "widgets": extract_widgets(m.agent_steps) if m.role == "assistant" else [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return rows[-limit:]


def _expiry() -> Optional[datetime]:
    return _now() + timedelta(days=settings.SHARE_EXPIRE_DAYS) if settings.SHARE_EXPIRE_DAYS > 0 else None


class ShareService:
    @staticmethod
    async def _owned(conversation_id: str, user_id: str, db: AsyncSession) -> Optional[Conversation]:
        return (await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))).scalar_one_or_none()

    @staticmethod
    async def get(conversation_id: str, user_id: str, db: AsyncSession) -> Optional[SharedConversation]:
        rec = (await db.execute(select(SharedConversation).where(SharedConversation.conversation_id == conversation_id, SharedConversation.user_id == user_id))).scalar_one_or_none()
        if rec and rec.expires_at and rec.expires_at < _now():
            return None
        return rec

    @staticmethod
    async def share(conversation_id: str, user_id: str, db: AsyncSession) -> Optional[SharedConversation]:
        """공유 링크를 만든다. 이미 있으면 같은 주소에서 내용만 지금 대화로 바꾼다. 대화가 없으면 None, 공유할 글이 없으면 ValueError."""
        conv = await ShareService._owned(conversation_id, user_id, db)
        if conv is None:
            return None
        snapshot = build_snapshot(await ChatService.get_messages(conversation_id, db))
        if not snapshot:
            raise ValueError("공유할 내용이 없습니다. 대화를 시작한 뒤 공유하세요")
        rec = (await db.execute(select(SharedConversation).where(SharedConversation.conversation_id == conversation_id))).scalar_one_or_none()
        if rec is None:
            rec = SharedConversation(conversation_id=conversation_id, user_id=user_id, token=secrets.token_urlsafe(24))
            db.add(rec)
        rec.title = (conv.title or "대화")[:255]
        rec.snapshot, rec.message_count = snapshot, len(snapshot)
        rec.expires_at, rec.updated_at = _expiry(), datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(rec)
        return rec

    @staticmethod
    async def unshare(conversation_id: str, user_id: str, db: AsyncSession) -> bool:
        r = await db.execute(delete(SharedConversation).where(SharedConversation.conversation_id == conversation_id, SharedConversation.user_id == user_id))
        await db.commit()
        return (r.rowcount or 0) > 0

    @staticmethod
    async def public(token: str, db: AsyncSession) -> Optional[SharedConversation]:
        """링크로 읽기. 없는 토큰·만료·형식 오류는 모두 같은 None (존재 여부를 알려 주지 않는다)."""
        if not TOKEN_RE.match(token or ""):
            return None
        rec = (await db.execute(select(SharedConversation).where(SharedConversation.token == token))).scalar_one_or_none()
        if rec is None or (rec.expires_at and rec.expires_at < _now()):
            return None
        try:  # 조회 수는 참고용이라 실패해도 읽기는 계속한다
            await db.execute(update(SharedConversation).where(SharedConversation.id == rec.id).values(view_count=SharedConversation.view_count + 1))
            await db.commit()
        except Exception:  # noqa: BLE001
            await db.rollback()
        return rec

"""사용자의 대화방 검색: 대화 제목과 메시지 내용에서 찾아 대화방별로 묶어 돌려준다."""
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message

MAX_QUERY = 100
MAX_CONVERSATIONS = 30
MAX_MESSAGE_ROWS = 400  # 메시지 일치 후보 (최근 것부터)
SNIPPETS_PER_CONVERSATION = 2
SNIPPET_RADIUS = 45


def like_pattern(q: str) -> str:
    """LIKE 와일드카드(% _)와 이스케이프 문자를 글자 그대로 찾도록 이스케이프한다."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def make_snippet(text: str, q: str, radius: int = SNIPPET_RADIUS) -> str:
    """검색어가 처음 나온 위치 주변을 잘라 한 줄로 보여 준다. 앞뒤가 잘렸으면 …을 붙인다."""
    flat = " ".join((text or "").split())
    i = flat.lower().find(q.lower())
    if i < 0:
        return flat[: radius * 2] + ("…" if len(flat) > radius * 2 else "")
    start, end = max(0, i - radius), min(len(flat), i + len(q) + radius)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")


async def search_conversations(user_id: str, query: str, db: AsyncSession) -> list[dict]:
    """[{conversation_id, title, updated_at, title_match, snippets: [{message_id, role, text, created_at}]}] 최근 순."""
    q = " ".join((query or "").split())[:MAX_QUERY]
    if not q:
        return []
    pat = like_pattern(q)

    title_rows = (
        await db.execute(
            select(Conversation.id, Conversation.title, Conversation.updated_at)
            .where(Conversation.user_id == user_id, Conversation.is_test.is_(False), Conversation.title.like(pat, escape="\\"))
            .order_by(Conversation.updated_at.desc())
            .limit(MAX_CONVERSATIONS)
        )
    ).all()

    msg_rows = (
        await db.execute(
            select(Message.id, Message.conversation_id, Message.role, Message.content, Message.created_at,
                   Conversation.title, Conversation.updated_at)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.user_id == user_id,
                Conversation.is_test.is_(False),
                Message.role.in_(("user", "assistant")),
                Message.content.like(pat, escape="\\"),
                Message.content != "__error__",
            )
            .order_by(Message.created_at.desc())
            .limit(MAX_MESSAGE_ROWS)
        )
    ).all()

    found: dict[str, dict] = {}
    for cid, title, updated in title_rows:
        found[cid] = {"conversation_id": cid, "title": title, "updated_at": updated, "title_match": True, "snippets": []}
    for mid, cid, role, content, created, title, updated in msg_rows:
        item = found.setdefault(
            cid, {"conversation_id": cid, "title": title, "updated_at": updated, "title_match": False, "snippets": []}
        )
        if len(item["snippets"]) < SNIPPETS_PER_CONVERSATION:
            item["snippets"].append({"message_id": mid, "role": role, "text": make_snippet(content, q), "created_at": created})
    out = sorted(found.values(), key=lambda x: x["updated_at"] or 0, reverse=True)
    return out[:MAX_CONVERSATIONS]

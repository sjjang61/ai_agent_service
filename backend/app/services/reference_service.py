"""질문에 붙이는 '참조' (스페이스 페이지·이전 대화): 소유자 확인 후 내용을 읽어 에이전트 입력에 덧붙인다."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import render
from app.config import settings
from app.models.conversation import Conversation
from app.models.space import Page
from app.services.chat_service import ChatService

MAX_REFERENCES = 5
MESSAGES_PER_CONVERSATION = 30
MESSAGE_CLIP = 1500
KIND_LABEL = {"page": "페이지", "conversation": "이전 대화"}


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…(이하 생략)"


async def resolve_references(
    user_id: str, refs: list, db: AsyncSession, current_conversation_id: Optional[str] = None
) -> list[dict]:
    """[{type, id, title}] 를 읽어 [{type, id, title, text}] 로 만든다. 남의 것이거나 없으면 404."""
    if len(refs) > MAX_REFERENCES:
        raise HTTPException(status_code=400, detail=f"참조는 최대 {MAX_REFERENCES}개까지 붙일 수 있습니다")
    out: list[dict] = []
    seen: set = set()
    for r in refs:
        rtype, rid = r.type, r.id
        if (rtype, rid) in seen:
            continue
        seen.add((rtype, rid))
        limit = settings.REFERENCE_MAX_CHARS
        if rtype == "page":
            page = (await db.execute(
                select(Page).where(Page.id == rid, Page.user_id == user_id, Page.deleted_at.is_(None))
            )).scalar_one_or_none()
            if page is None:
                raise HTTPException(status_code=404, detail="참조한 페이지를 찾을 수 없습니다")
            out.append({"type": "page", "id": rid, "title": page.title or "제목 없음", "text": _clip(page.content or "(내용 없음)", limit)})
        else:
            if rid == current_conversation_id:
                continue  # 지금 대화는 이미 맥락에 있다
            conv = await db.get(Conversation, rid)
            if conv is None or conv.user_id != user_id or conv.is_test:
                raise HTTPException(status_code=404, detail="참조한 대화를 찾을 수 없습니다")
            msgs = [m for m in await ChatService.get_messages(rid, db) if m.role in ("user", "assistant") and m.content != "__error__"]
            lines = [
                f"{'사용자' if m.role == 'user' else '에이전트'}: {_clip((m.content or '').strip(), MESSAGE_CLIP)}"
                for m in msgs[-MESSAGES_PER_CONVERSATION:]
            ]
            # 오래된 앞부분이 아니라 최근 대화를 남긴다
            text = "\n\n".join(lines)
            if len(text) > limit:
                text = "…(앞부분 생략)\n" + text[-limit:]
            out.append({"type": "conversation", "id": rid, "title": conv.title or "대화", "text": text or "(메시지 없음)"})
    return out


def compose_with_references(content: str, refs: Optional[list]) -> str:
    """사용자 입력 뒤에 참조 자료 블록을 덧붙인다 (참조가 없으면 그대로)."""
    if not refs:
        return content
    items = "\n\n".join(render("reference_item", kind=KIND_LABEL[r["type"]], title=r["title"], text=r["text"]) for r in refs)
    block = render("reference_context", items=items)
    return f"{content}\n\n{block}" if content else block


def reference_note(refs: Optional[list]) -> str:
    """지난 턴의 참조는 본문 대신 제목만 짧게 남긴다 (대화 기록이 커지는 것을 막는다)."""
    if not refs:
        return ""
    return render("reference_note", titles=", ".join(r.get("title", "") for r in refs))


def public_refs(refs: Optional[list]) -> list[dict]:
    """화면·API 에 내보낼 때는 본문(text)을 뺀다."""
    return [{"type": r["type"], "id": r["id"], "title": r.get("title", "")} for r in (refs or [])]

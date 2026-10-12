import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import AgentOrchestrator
from app.db.session import get_session
from app.core.forms import PendingForms
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    convs = await ChatService.get_conversations(current_user.id, db)
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            llm_provider=c.llm_provider,
            model_name=c.model_name,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    conv = await ChatService.create_conversation(current_user.id, data, db)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        llm_provider=conv.llm_provider,
        model_name=conv.model_name,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await ChatService.delete_conversation(conversation_id, current_user.id, db)
    return {"status": "deleted"}


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    messages = await ChatService.get_messages(conversation_id, db)
    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            agent_steps=m.agent_steps or [],
            tool_calls=m.tool_calls or [],
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await ChatService.save_message(conversation_id, "user", data.content, db)

    async def event_stream():
        orchestrator = AgentOrchestrator(
            current_user.id,
            llm_provider=data.llm_provider,
            model=data.model,
        )
        full_response = ""
        agent_steps = []
        has_error = False
        try:
            async for event in orchestrator.run(data.content, conversation_id, db):
                if event["type"] == "token":
                    full_response += event.get("content", "")
                elif event["type"] in ("thought", "tool_call", "tool_result"):
                    agent_steps.append(event)
                elif event["type"] == "error":
                    has_error = True
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error("[chat] agent 실행 오류: %s", e, exc_info=True)
            has_error = True
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if full_response or has_error:
                save_content = full_response if full_response else "__error__"
                msg = await ChatService.save_message(
                    conversation_id, "assistant", save_content, db, agent_steps=agent_steps
                )
                yield f"data: {json.dumps({'type': 'done', 'message_id': msg.id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
class FormAnswerRequest(BaseModel):
    answers: Optional[Dict[str, Any]] = None
    cancelled: bool = False


@router.post("/conversations/{conversation_id}/form-answer")
async def answer_form(
    conversation_id: str,
    data: FormAnswerRequest,
    current_user: User = Depends(get_current_user),
):
    """form_ask_user 로 대기 중인 에이전트에게 사용자의 응답(또는 취소)을 전달한다."""
    try:
        delivered = PendingForms.answer(conversation_id, current_user.id, data.answers, data.cancelled)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not delivered:
        raise HTTPException(status_code=404, detail="대기 중인 폼이 없습니다 (이미 응답했거나 시간이 초과되었습니다)")
    return {"status": "ok"}



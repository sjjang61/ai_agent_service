import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 사용자가 실행을 중단했을 때 저장되는 응답 끝에 붙는 안내 (UI 에도 그대로 보인다)
CANCEL_NOTE = "_(사용자가 실행을 중단했습니다)_"
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import AgentOrchestrator
from app.db.session import get_session
from app.core.forms import PendingForms
from app.core.runs import RunRegistry, cancellable_events
from app.services.attachment_service import compose_with_attachments, validate_attachments
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
    try:
        # 예약 작업의 결과 대화를 열었다면 그 실행 결과는 읽은 것으로 처리한다 (아이콘 바의 읽지 않음 표시 해제)
        from app.services.schedule_service import ScheduleService

        await ScheduleService.mark_conversation_read(conversation_id, current_user.id, db)
    except Exception:
        logger.exception("[chat] 예약 결과 읽음 처리 실패")
    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            agent_steps=m.agent_steps or [],
            tool_calls=m.tool_calls or [],
            attachments=(m.metadata_ or {}).get("attachments", []),
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
    attachments = validate_attachments(data.attachments)
    if not data.content.strip() and not attachments:
        raise HTTPException(status_code=400, detail="메시지 또는 첨부 파일이 필요합니다")
    if RunRegistry.is_running(conversation_id):
        raise HTTPException(status_code=409, detail="이 대화에서 이미 에이전트가 실행 중입니다")
    await ChatService.save_message(conversation_id, "user", data.content, db, attachments=attachments)
    user_input = compose_with_attachments(data.content, attachments)

    async def persist_partial(content: str, steps: list):
        """연결이 끊긴 요청의 DB 세션은 이미 닫혔을 수 있어 새 세션으로 저장한다."""
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await ChatService.save_message(conversation_id, "assistant", content, s, agent_steps=steps)

    async def event_stream():
        orchestrator = AgentOrchestrator(
            current_user.id,
            llm_provider=data.llm_provider,
            model=data.model,
            user_timezone=data.timezone,
        )
        full_response = ""
        agent_steps = []
        has_error = False
        cancelled = False
        try:
            source = orchestrator.run(user_input, conversation_id, db)
            async for event in cancellable_events(conversation_id, current_user.id, source):
                if event["type"] == "token":
                    full_response += event.get("content", "")
                elif event["type"] in ("thought", "tool_call", "tool_result"):
                    agent_steps.append(event)
                elif event["type"] == "error":
                    has_error = True
                elif event["type"] == "cancelled":
                    cancelled = True
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            # 클라이언트 연결이 끊김: 지금까지의 결과를 백그라운드로 저장하고 종료
            note = full_response + ("\n\n" if full_response else "") + CANCEL_NOTE
            asyncio.create_task(persist_partial(note, agent_steps))
            raise
        except Exception as e:
            logger.error("[chat] agent 실행 오류: %s", e, exc_info=True)
            has_error = True
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        if cancelled:
            note = full_response + ("\n\n" if full_response else "") + CANCEL_NOTE
            msg = await ChatService.save_message(conversation_id, "assistant", note, db, agent_steps=agent_steps)
            yield f"data: {json.dumps({'type': 'done', 'message_id': msg.id})}\n\n"
        elif full_response or has_error:
            save_content = full_response if full_response else "__error__"
            msg = await ChatService.save_message(
                conversation_id, "assistant", save_content, db, agent_steps=agent_steps
            )
            yield f"data: {json.dumps({'type': 'done', 'message_id': msg.id})}\n\n"

            # 메모리 자동 추출 (백그라운드 — 새 세션 사용)
            if full_response and not has_error:
                from app.services.memory_extractor import maybe_extract_memories
                from app.db.session import AsyncSessionLocal

                async def extract_with_new_session():
                    async with AsyncSessionLocal() as new_db:
                        await maybe_extract_memories(
                            user_id=current_user.id,
                            conversation_id=conversation_id,
                            user_message=user_input,
                            agent_response=full_response,
                            db=new_db,
                        )

                asyncio.create_task(extract_with_new_session())

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


@router.post("/conversations/{conversation_id}/cancel")
async def cancel_run(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """이 대화에서 실행 중인 에이전트를 취소한다. 진행 중인 LLM 호출·도구 대기가 중단되고 지금까지의 결과가 저장된다."""
    if not RunRegistry.cancel(conversation_id, current_user.id):
        raise HTTPException(status_code=404, detail="실행 중인 작업이 없습니다")
    return {"status": "cancelling"}

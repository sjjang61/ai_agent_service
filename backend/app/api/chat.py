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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.orchestrator import AgentOrchestrator
from app.db.session import get_session
from app.core.forms import PendingForms
from app.core.runs import RunRegistry, cancellable_events
from app.services.attachment_service import compose_with_attachments, validate_attachments
from app.services.reference_service import compose_with_references, public_refs, resolve_references
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


async def _conversation_responses(convs: list, db: AsyncSession) -> List[ConversationResponse]:
    """대화 목록 응답. 커스텀 에이전트 대화에는 에이전트 이름·아이콘·버전을 붙인다."""
    from app.models.agent import Agent, AgentVersion

    agent_ids = {c.agent_id for c in convs if c.agent_id}
    agents, versions = {}, {}
    if agent_ids:
        agents = {a.id: a for a in (await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))).scalars().all()}
        vids = {c.agent_version_id for c in convs if c.agent_version_id}
        if vids:
            versions = {v.id: v.version for v in (await db.execute(select(AgentVersion).where(AgentVersion.id.in_(vids)))).scalars().all()}
    out = []
    for c in convs:
        a = agents.get(c.agent_id) if c.agent_id else None
        out.append(ConversationResponse(
            id=c.id, title=c.title, llm_provider=c.llm_provider, model_name=c.model_name,
            agent_id=c.agent_id if a else None, agent_name=a.name if a else None, agent_icon=a.icon if a else None,
            agent_version=versions.get(c.agent_version_id), is_test=bool(c.is_test), space_id=c.space_id,
            created_at=c.created_at, updated_at=c.updated_at,
        ))
    return out


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    return await _conversation_responses(await ChatService.get_conversations(current_user.id, db), db)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    conv = await ChatService.create_conversation(current_user.id, data, db)
    return (await _conversation_responses([conv], db))[0]


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
            references=public_refs((m.metadata_ or {}).get("references")),
            memory_saved=(m.metadata_ or {}).get("memory_saved", []),
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
    from app.agent.agent_runtime import memory_enabled
    from app.models.conversation import Conversation
    from app.schemas.agent import AgentConfig
    from app.services.agent_service import AgentService

    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다")
    override = None
    if data.agent_config is not None and conv.is_test:  # 저장하지 않은 편집 내용으로 미리보기
        try:
            override = AgentConfig.model_validate(data.agent_config)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"에이전트 설정이 올바르지 않습니다: {e}")
    runtime = await AgentService.runtime_for_conversation(conv, db, override)
    use_memory_extraction = memory_enabled(runtime) and not conv.is_test

    attachments = validate_attachments(data.attachments)
    if not data.content.strip() and not attachments:
        raise HTTPException(status_code=400, detail="메시지 또는 첨부 파일이 필요합니다")
    if RunRegistry.is_running(conversation_id):
        raise HTTPException(status_code=409, detail="이 대화에서 이미 에이전트가 실행 중입니다")
    references = await resolve_references(current_user.id, data.references, db, current_conversation_id=conversation_id)
    await ChatService.save_message(conversation_id, "user", data.content, db, attachments=attachments, references=references)
    text_input = compose_with_attachments(data.content, attachments)  # 메모리 추출에는 참조 본문을 넣지 않는다 (참조 자료는 사용자 발화가 아니다)
    user_input = compose_with_references(text_input, references)

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
            runtime=runtime,
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

            # 컨텍스트 창에서 밀려난 오래된 메시지를 백그라운드에서 요약 (응답과 무관하게 실행)
            from app.services.conversation_summary import maybe_update_summary

            asyncio.create_task(maybe_update_summary(conversation_id))

            # 메모리 자동 추출: 응답은 이미 전달했으므로 사용자는 기다리지 않는다.
            # 저장된 항목이 있으면 같은 스트림으로 알려 주고 메시지에도 남긴다 (새로고침 후에도 표시).
            if full_response and not has_error and use_memory_extraction:
                from app.services.memory_extractor import maybe_extract_memories
                from app.db.session import AsyncSessionLocal

                async with AsyncSessionLocal() as mem_db:
                    saved = await maybe_extract_memories(
                        user_id=current_user.id,
                        conversation_id=conversation_id,
                        user_message=text_input,
                        agent_response=full_response,
                        db=mem_db,
                    )
                if saved:
                    msg.metadata_ = {**(msg.metadata_ or {}), "memory_saved": saved}
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'memory_saved', 'items': saved, 'message_id': msg.id})}\n\n"

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

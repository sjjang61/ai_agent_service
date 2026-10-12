from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent.orchestrator import AgentOrchestrator
from app.core.websocket import ws_manager
from app.db.session import AsyncSessionLocal
from app.services.attachment_service import compose_with_attachments, validate_attachments
from app.services.chat_service import ChatService

router = APIRouter()


async def _get_user_from_token(token: str):
    from app.core.security import decode_token
    from app.models.user import User
    from sqlalchemy import select

    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == payload.get("sub")))
        return result.scalar_one_or_none()


@router.websocket("/chat/{conversation_id}")
async def chat_websocket(conversation_id: str, websocket: WebSocket):
    token = websocket.query_params.get("token")
    current_user = await _get_user_from_token(token)
    if not current_user:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(conversation_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "message":
                user_content = data.get("content", "")
                try:
                    attachments = validate_attachments(data.get("attachments"))
                except Exception as e:
                    await ws_manager.send_event(conversation_id, {"type": "error", "message": str(getattr(e, "detail", e))})
                    continue
                agent_input = compose_with_attachments(user_content, attachments)
                async with AsyncSessionLocal() as db:
                    await ChatService.save_message(conversation_id, "user", user_content, db, attachments=attachments)
                    orchestrator = AgentOrchestrator(
                        current_user.id,
                        llm_provider=data.get("llm_provider"),
                        model=data.get("model"),
                    )
                    full_response = ""
                    agent_steps = []
                    try:
                        async for event in orchestrator.run(agent_input, conversation_id, db):
                            await ws_manager.send_event(conversation_id, event)
                            if event["type"] == "token":
                                full_response += event.get("content", "")
                            elif event["type"] in ("thought", "tool_call", "tool_result"):
                                agent_steps.append(event)
                    except Exception as e:
                        await ws_manager.send_event(
                            conversation_id, {"type": "error", "message": str(e)}
                        )
                    if full_response:
                        msg = await ChatService.save_message(
                            conversation_id,
                            "assistant",
                            full_response,
                            db,
                            agent_steps=agent_steps,
                        )
                        await ws_manager.send_event(
                            conversation_id, {"type": "done", "message_id": msg.id}
                        )
    except WebSocketDisconnect:
        await ws_manager.disconnect(conversation_id, websocket)

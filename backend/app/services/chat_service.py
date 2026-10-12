from datetime import datetime, timezone
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import normalize_llm_type, settings
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ConversationCreate


class ChatService:
    @staticmethod
    async def get_conversations(user_id: str, db: AsyncSession) -> List[Conversation]:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_conversation(
        user_id: str, data: ConversationCreate, db: AsyncSession
    ) -> Conversation:
        llm_type = normalize_llm_type(data.llm_provider or settings.LLM_TYPE)
        conv = Conversation(
            user_id=user_id,
            title=data.title,
            llm_provider=llm_type,
            model_name=data.model_name or settings.default_model_for(llm_type),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv

    @staticmethod
    async def get_messages(conversation_id: str, db: AsyncSession) -> List[Message]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save_message(
        conversation_id: str,
        role: str,
        content: str,
        db: AsyncSession,
        agent_steps: list = None,
        tool_calls: list = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_steps=agent_steps or [],
            tool_calls=tool_calls or [],
        )
        db.add(msg)

        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv:
            conv.updated_at = datetime.now(timezone.utc)
            if role == "user" and conv.title == "New Conversation":
                conv.title = content[:50]

        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def delete_conversation(
        conversation_id: str, user_id: str, db: AsyncSession
    ):
        await db.execute(
            delete(Message).where(Message.conversation_id == conversation_id)
        )
        await db.execute(
            delete(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        await db.commit()

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
    async def get_conversations(user_id: str, db: AsyncSession, include_test: bool = False) -> List[Conversation]:
        query = select(Conversation).where(Conversation.user_id == user_id)
        if not include_test:
            query = query.where(Conversation.is_test.is_(False))  # 에이전트 빌더의 미리보기 대화는 목록에서 숨긴다
        result = await db.execute(query.order_by(Conversation.updated_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def create_conversation(
        user_id: str, data: ConversationCreate, db: AsyncSession
    ) -> Conversation:
        llm_type = normalize_llm_type(data.llm_provider or settings.LLM_TYPE)
        agent_id = agent_version_id = None
        if data.agent_id:
            from app.services.agent_service import AgentService

            if data.is_test:  # 미리보기: 발행 여부와 무관하게 초안으로 실행
                agent = await AgentService.get(user_id, data.agent_id, db)
            else:  # 일반 대화: 지금 발행된 버전에 고정한다
                agent, ver = await AgentService.require_published(user_id, data.agent_id, db)
                agent_version_id = ver.id
            agent_id = agent.id
        conv = Conversation(
            user_id=user_id,
            title=data.title,
            llm_provider=llm_type,
            model_name=data.model_name or settings.default_model_for(llm_type),
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            is_test=bool(data.is_test and agent_id),
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
        attachments: list = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent_steps=agent_steps or [],
            tool_calls=tool_calls or [],
            metadata_={"attachments": attachments} if attachments else {},
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
        # 벡터 컬렉션 삭제 (RAG 문서)
        from app.core.vector_store import VectorStoreManager
        VectorStoreManager.delete_collection(conversation_id)

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

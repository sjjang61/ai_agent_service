from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsage
from app.models.user import User


class TokenUsageService:
    @staticmethod
    async def record_usage(
        db: AsyncSession,
        user_id: str,
        conversation_id: str,
        llm_provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        message_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> TokenUsage:
        usage = TokenUsage(
            message_id=message_id,
            user_id=user_id,
            conversation_id=conversation_id,
            llm_provider=llm_provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name=agent_name,
        )
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
        return usage

    @staticmethod
    async def get_summary(
        db: AsyncSession, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        query = select(
            func.count(TokenUsage.id).label("total_requests"),
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("total_output_tokens"),
        )
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)

        result = await db.execute(query)
        row = result.one()
        return {
            "total_requests": row.total_requests or 0,
            "total_input_tokens": int(row.total_input_tokens),
            "total_output_tokens": int(row.total_output_tokens),
            "total_tokens": int(row.total_input_tokens) + int(row.total_output_tokens),
        }

    @staticmethod
    async def get_daily_usage(
        db: AsyncSession,
        days: int = 30,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                func.date(TokenUsage.created_at).label("date"),
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= start_date)
            .group_by(func.date(TokenUsage.created_at))
            .order_by(func.date(TokenUsage.created_at))
        )

        if user_id:
            query = query.where(TokenUsage.user_id == user_id)

        result = await db.execute(query)
        return [
            {
                "date": str(row.date),
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_weekly_usage(
        db: AsyncSession,
        weeks: int = 12,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(weeks=weeks)

        query = (
            select(
                extract("year", TokenUsage.created_at).label("year"),
                extract("week", TokenUsage.created_at).label("week"),
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= start_date)
            .group_by(
                extract("year", TokenUsage.created_at),
                extract("week", TokenUsage.created_at),
            )
            .order_by(
                extract("year", TokenUsage.created_at),
                extract("week", TokenUsage.created_at),
            )
        )

        if user_id:
            query = query.where(TokenUsage.user_id == user_id)

        result = await db.execute(query)
        return [
            {
                "date": f"{int(row.year)}-W{int(row.week):02d}",
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_monthly_usage(
        db: AsyncSession,
        months: int = 12,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=months * 30)

        query = (
            select(
                extract("year", TokenUsage.created_at).label("year"),
                extract("month", TokenUsage.created_at).label("month"),
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= start_date)
            .group_by(
                extract("year", TokenUsage.created_at),
                extract("month", TokenUsage.created_at),
            )
            .order_by(
                extract("year", TokenUsage.created_at),
                extract("month", TokenUsage.created_at),
            )
        )

        if user_id:
            query = query.where(TokenUsage.user_id == user_id)

        result = await db.execute(query)
        return [
            {
                "date": f"{int(row.year)}-{int(row.month):02d}",
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_user_breakdown(
        db: AsyncSession,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                User.id,
                User.email,
                User.display_name,
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .join(User, TokenUsage.user_id == User.id)
            .where(TokenUsage.created_at >= start_date)
            .group_by(User.id, User.email, User.display_name)
            .order_by(
                (func.sum(TokenUsage.input_tokens) + func.sum(TokenUsage.output_tokens)).desc()
            )
        )

        result = await db.execute(query)
        return [
            {
                "user_id": row.id,
                "email": row.email,
                "display_name": row.display_name or row.email,
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_model_breakdown(
        db: AsyncSession,
        days: int = 30,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                TokenUsage.llm_provider,
                TokenUsage.model_name,
                func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(TokenUsage.created_at >= start_date)
            .group_by(TokenUsage.llm_provider, TokenUsage.model_name)
            .order_by(
                (func.sum(TokenUsage.input_tokens) + func.sum(TokenUsage.output_tokens)).desc()
            )
        )

        if user_id:
            query = query.where(TokenUsage.user_id == user_id)

        result = await db.execute(query)
        return [
            {
                "llm_provider": row.llm_provider,
                "model_name": row.model_name,
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "total_tokens": int(row.input_tokens) + int(row.output_tokens),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_session_usage(
        db: AsyncSession,
        conversation_id: str,
    ) -> Dict[str, Any]:
        query = select(
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
            func.count(TokenUsage.id).label("request_count"),
        ).where(TokenUsage.conversation_id == conversation_id)

        result = await db.execute(query)
        row = result.one()
        return {
            "conversation_id": conversation_id,
            "input_tokens": int(row.input_tokens),
            "output_tokens": int(row.output_tokens),
            "total_tokens": int(row.input_tokens) + int(row.output_tokens),
            "request_count": row.request_count or 0,
        }

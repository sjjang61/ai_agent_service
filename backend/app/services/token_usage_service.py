from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage import TokenUsage
from app.models.user import User
from app.services.pricing import estimate_cost_usd, refresh_if_stale


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
    async def record_usage_detached(**kwargs) -> None:
        """요청과 별개의 DB 세션으로 사용량을 기록한다. 응답이 끝나는 순간 요청이 취소되거나 연결이 끊겨도
        (요청의 세션·연결은 그때 함께 취소된다) 기록이 유실되거나 오류 로그가 쏟아지지 않게 한다."""
        import logging

        from app.db.session import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                await TokenUsageService.record_usage(db=session, **kwargs)
        except Exception as e:  # noqa: BLE001  (취소 포함: 부가 기록이라 응답에 영향을 주지 않는다)
            logging.getLogger(__name__).warning("[usage] 토큰 사용량 기록 실패: %s: %s", type(e).__name__, e)

    @staticmethod
    def _fold(rows, bucket_of) -> dict:
        """(버킷, 모델)별 행을 버킷별로 합친다. 모델마다 단가가 달라 비용은 모델별로 계산한 뒤 더한다."""
        out: dict = {}
        for r in rows:
            acc = out.setdefault(bucket_of(r), {"input": 0, "output": 0, "requests": 0, "cost": 0.0, "incomplete": False})
            inp, outp = int(r.input_tokens), int(r.output_tokens)
            acc["input"] += inp
            acc["output"] += outp
            acc["requests"] += int(r.request_count)
            cost = estimate_cost_usd(r.model_name, inp, outp)
            if cost is None:
                if inp or outp:
                    acc["incomplete"] = True  # 단가를 모르는 모델 (비용에서 빠진다)
            else:
                acc["cost"] += cost
        return out

    @staticmethod
    def _row(acc: dict) -> Dict[str, Any]:
        return {
            "input_tokens": acc["input"],
            "output_tokens": acc["output"],
            "total_tokens": acc["input"] + acc["output"],
            "cost_usd": round(acc["cost"], 6),
            "cost_incomplete": acc["incomplete"],
        }

    @staticmethod
    def _sums():
        return (
            TokenUsage.model_name,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
            func.count(TokenUsage.id).label("request_count"),
        )

    @staticmethod
    async def get_summary(
        db: AsyncSession, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        await refresh_if_stale(db)
        query = select(*TokenUsageService._sums()).group_by(TokenUsage.model_name)
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        folded = TokenUsageService._fold((await db.execute(query)).all(), lambda r: "all")
        acc = folded.get("all", {"input": 0, "output": 0, "requests": 0, "cost": 0.0, "incomplete": False})
        return {
            "total_requests": acc["requests"],
            "total_input_tokens": acc["input"],
            "total_output_tokens": acc["output"],
            "total_tokens": acc["input"] + acc["output"],
            "cost_usd": round(acc["cost"], 6),
            "cost_incomplete": acc["incomplete"],
        }

    @staticmethod
    async def get_daily_usage(
        db: AsyncSession,
        days: int = 30,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await refresh_if_stale(db)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        day = func.date(TokenUsage.created_at)
        query = (
            select(day.label("date"), *TokenUsageService._sums())
            .where(TokenUsage.created_at >= start_date)
            .group_by(day, TokenUsage.model_name)
            .order_by(day)
        )
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        folded = TokenUsageService._fold((await db.execute(query)).all(), lambda r: str(r.date))
        return [{"date": k, **TokenUsageService._row(v), "request_count": v["requests"]} for k, v in sorted(folded.items())]

    @staticmethod
    async def get_weekly_usage(
        db: AsyncSession,
        weeks: int = 12,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await refresh_if_stale(db)
        start_date = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        year, week = extract("year", TokenUsage.created_at), extract("week", TokenUsage.created_at)
        query = (
            select(year.label("year"), week.label("week"), *TokenUsageService._sums())
            .where(TokenUsage.created_at >= start_date)
            .group_by(year, week, TokenUsage.model_name)
            .order_by(year, week)
        )
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        folded = TokenUsageService._fold((await db.execute(query)).all(), lambda r: f"{int(r.year)}-W{int(r.week):02d}")
        return [{"date": k, **TokenUsageService._row(v), "request_count": v["requests"]} for k, v in sorted(folded.items())]

    @staticmethod
    async def get_monthly_usage(
        db: AsyncSession,
        months: int = 12,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await refresh_if_stale(db)
        start_date = datetime.now(timezone.utc) - timedelta(days=months * 30)
        year, month = extract("year", TokenUsage.created_at), extract("month", TokenUsage.created_at)
        query = (
            select(year.label("year"), month.label("month"), *TokenUsageService._sums())
            .where(TokenUsage.created_at >= start_date)
            .group_by(year, month, TokenUsage.model_name)
            .order_by(year, month)
        )
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        folded = TokenUsageService._fold((await db.execute(query)).all(), lambda r: f"{int(r.year)}-{int(r.month):02d}")
        return [{"date": k, **TokenUsageService._row(v), "request_count": v["requests"]} for k, v in sorted(folded.items())]

    @staticmethod
    async def get_user_breakdown(
        db: AsyncSession,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        await refresh_if_stale(db)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = (
            select(User.id, User.email, User.display_name, *TokenUsageService._sums())
            .join(User, TokenUsage.user_id == User.id)
            .where(TokenUsage.created_at >= start_date)
            .group_by(User.id, User.email, User.display_name, TokenUsage.model_name)
        )
        rows = (await db.execute(query)).all()
        who = {r.id: (r.email, r.display_name or r.email) for r in rows}
        folded = TokenUsageService._fold(rows, lambda r: r.id)
        out = [
            {"user_id": uid, "email": who[uid][0], "display_name": who[uid][1], **TokenUsageService._row(v), "request_count": v["requests"]}
            for uid, v in folded.items()
        ]
        return sorted(out, key=lambda x: x["total_tokens"], reverse=True)

    @staticmethod
    async def get_model_breakdown(
        db: AsyncSession,
        days: int = 30,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await refresh_if_stale(db)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = (
            select(TokenUsage.llm_provider, *TokenUsageService._sums())
            .where(TokenUsage.created_at >= start_date)
            .group_by(TokenUsage.llm_provider, TokenUsage.model_name)
        )
        if user_id:
            query = query.where(TokenUsage.user_id == user_id)
        rows = (await db.execute(query)).all()
        folded = TokenUsageService._fold(rows, lambda r: (r.llm_provider, r.model_name))
        out = [
            {"llm_provider": prov, "model_name": model, **TokenUsageService._row(v), "request_count": v["requests"]}
            for (prov, model), v in folded.items()
        ]
        return sorted(out, key=lambda x: x["total_tokens"], reverse=True)

    @staticmethod
    async def get_session_usage(
        db: AsyncSession,
        conversation_id: str,
    ) -> Dict[str, Any]:
        await refresh_if_stale(db)
        query = (
            select(*TokenUsageService._sums())
            .where(TokenUsage.conversation_id == conversation_id)
            .group_by(TokenUsage.model_name)
        )
        folded = TokenUsageService._fold((await db.execute(query)).all(), lambda r: "all")
        acc = folded.get("all", {"input": 0, "output": 0, "requests": 0, "cost": 0.0, "incomplete": False})
        return {"conversation_id": conversation_id, **TokenUsageService._row(acc), "request_count": acc["requests"]}

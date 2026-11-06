"""사용자별 도구 활성화 설정. 꺼 둔 도구는 에이전트(채팅·예약·메신저 공통)가 쓰지 못한다."""
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_tool_setting import UserToolSetting


class ToolSettingsService:
    @staticmethod
    async def disabled_names(user_id: str, db: AsyncSession) -> set[str]:
        rows = await db.execute(
            select(UserToolSetting.tool_name).where(UserToolSetting.user_id == user_id, UserToolSetting.enabled.is_(False))
        )
        return set(rows.scalars().all())

    @staticmethod
    async def set_enabled(user_id: str, names: Iterable[str], enabled: bool, db: AsyncSession) -> None:
        names = list(dict.fromkeys(names))
        existing = {
            r.tool_name: r
            for r in (
                await db.execute(select(UserToolSetting).where(UserToolSetting.user_id == user_id, UserToolSetting.tool_name.in_(names)))
            ).scalars()
        }
        for n in names:
            if n in existing:
                existing[n].enabled = enabled
            elif not enabled:  # 켜는 것은 기본값이므로 행을 만들지 않는다
                db.add(UserToolSetting(user_id=user_id, tool_name=n, enabled=False))
        if enabled:  # 다시 켜면 행을 지워 기본 상태로 돌린다
            for r in existing.values():
                await db.delete(r)
        await db.commit()


def drop_disabled(tools: list, disabled: set[str]) -> list:
    """꺼 둔 도구를 목록에서 뺀다."""
    return [t for t in tools if t.name not in disabled] if disabled else tools

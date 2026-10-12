from typing import List

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_config import MCPServerConfig
from app.schemas.mcp import MCPServerCreate, MCPServerUpdate


class MCPService:
    @staticmethod
    async def get_user_configs(user_id: str, db: AsyncSession) -> List[MCPServerConfig]:
        """활성화된 MCP 서버만 반환 (Agent tool 로딩용)."""
        result = await db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.user_id == user_id,
                MCPServerConfig.is_active == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_configs(user_id: str, db: AsyncSession) -> List[MCPServerConfig]:
        """활성/비활성 모두 반환 (설정 UI용)."""
        result = await db.execute(
            select(MCPServerConfig)
            .where(MCPServerConfig.user_id == user_id)
            .order_by(MCPServerConfig.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def toggle_active(config_id: str, user_id: str, db: AsyncSession) -> MCPServerConfig:
        result = await db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.id == config_id,
                MCPServerConfig.user_id == user_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail="MCP config not found")
        config.is_active = not config.is_active
        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def create_config(
        user_id: str, data: MCPServerCreate, db: AsyncSession
    ) -> MCPServerConfig:
        config = MCPServerConfig(user_id=user_id, **data.model_dump())
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def update_config(
        config_id: str, user_id: str, data: MCPServerUpdate, db: AsyncSession
    ) -> MCPServerConfig:
        result = await db.execute(
            select(MCPServerConfig).where(
                MCPServerConfig.id == config_id,
                MCPServerConfig.user_id == user_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail="MCP config not found")
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(config, k, v)
        await db.commit()
        await db.refresh(config)
        return config

    @staticmethod
    async def delete_config(config_id: str, user_id: str, db: AsyncSession):
        await db.execute(
            delete(MCPServerConfig).where(
                MCPServerConfig.id == config_id,
                MCPServerConfig.user_id == user_id,
            )
        )
        await db.commit()

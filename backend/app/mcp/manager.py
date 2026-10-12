import logging
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPSessionManager:
    _sessions: Dict[str, Dict[str, MCPClient]] = {}

    @classmethod
    async def get_or_create_session(cls, user_id: str, config) -> MCPClient:
        user_sessions = cls._sessions.setdefault(user_id, {})
        existing = user_sessions.get(config.name)

        # 기존 세션이 있으면 연결 상태 확인 — 죽어 있으면 제거
        if existing is not None:
            if not existing.is_connected:
                logger.warning("[mcp] 죽은 세션 제거: user=%s server=%s", user_id, config.name)
                try:
                    await existing.disconnect()
                except Exception:
                    pass
                del user_sessions[config.name]
                existing = None

        if existing is None:
            client = MCPClient(config)
            await client.connect()
            user_sessions[config.name] = client
            return client

        return existing

    @classmethod
    async def get_tools(cls, user_id: str, db: AsyncSession) -> list:
        from app.services.mcp_service import MCPService

        configs = await MCPService.get_user_configs(user_id, db)
        all_tools = []
        for config in configs:
            try:
                client = await cls.get_or_create_session(user_id, config)
                all_tools.extend(client.to_langchain_tools())
            except Exception as e:
                # 연결 실패한 서버는 캐시에서도 제거 후 건너뜀
                user_sessions = cls._sessions.get(user_id, {})
                if config.name in user_sessions:
                    del user_sessions[config.name]
                logger.warning("[mcp] 서버 연결 실패 (건너뜀): server=%s error=%s", config.name, e)
        return all_tools

    @classmethod
    async def get_clients(cls, user_id: str, db: AsyncSession) -> Dict[str, MCPClient]:
        """연결된 MCP 서버 클라이언트 {server_name: MCPClient}. 연결 실패한 서버는 제외."""
        from app.services.mcp_service import MCPService

        configs = await MCPService.get_user_configs(user_id, db)
        clients: Dict[str, MCPClient] = {}
        for config in configs:
            try:
                clients[config.name] = await cls.get_or_create_session(user_id, config)
            except Exception as e:
                user_sessions = cls._sessions.get(user_id, {})
                user_sessions.pop(config.name, None)
                logger.warning("[mcp] 서버 연결 실패 (건너뜀): server=%s error=%s", config.name, e)
        return clients

    @classmethod
    async def reload_session(cls, user_id: str, server_name: str):
        user_sessions = cls._sessions.get(user_id, {})
        if server_name in user_sessions:
            try:
                await user_sessions[server_name].disconnect()
            except Exception:
                pass
            del user_sessions[server_name]

    @classmethod
    async def cleanup(cls):
        for user_sessions in cls._sessions.values():
            for client in user_sessions.values():
                try:
                    await client.disconnect()
                except Exception:
                    pass
        cls._sessions.clear()

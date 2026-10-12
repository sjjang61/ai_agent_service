from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.mcp.manager import MCPSessionManager
from app.models.user import User
from app.schemas.mcp import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MCPToolResponse,
)
from app.services.mcp_service import MCPService

router = APIRouter()


@router.get("/configs", response_model=List[MCPServerResponse])
async def list_configs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    configs = await MCPService.get_all_configs(current_user.id, db)
    return [
        MCPServerResponse(
            id=c.id,
            name=c.name,
            display_name=c.display_name,
            transport=c.transport,
            command=c.command,
            args=c.args or [],
            url=c.url,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in configs
    ]


@router.post("/configs", response_model=MCPServerResponse)
async def create_config(
    data: MCPServerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    config = await MCPService.create_config(current_user.id, data, db)
    return MCPServerResponse(
        id=config.id,
        name=config.name,
        display_name=config.display_name,
        transport=config.transport,
        command=config.command,
        args=config.args or [],
        url=config.url,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.put("/configs/{config_id}", response_model=MCPServerResponse)
async def update_config(
    config_id: str,
    data: MCPServerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    config = await MCPService.update_config(config_id, current_user.id, data, db)
    return MCPServerResponse(
        id=config.id,
        name=config.name,
        display_name=config.display_name,
        transport=config.transport,
        command=config.command,
        args=config.args or [],
        url=config.url,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.post("/configs/{config_id}/toggle", response_model=MCPServerResponse)
async def toggle_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """활성/비활성 토글. 비활성화 시 기존 세션도 제거."""
    config = await MCPService.toggle_active(config_id, current_user.id, db)
    if not config.is_active:
        await MCPSessionManager.reload_session(current_user.id, config.name)
    return MCPServerResponse(
        id=config.id,
        name=config.name,
        display_name=config.display_name,
        transport=config.transport,
        command=config.command,
        args=config.args or [],
        url=config.url,
        is_active=config.is_active,
        created_at=config.created_at,
    )


@router.delete("/configs/{config_id}")
async def delete_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await MCPService.delete_config(config_id, current_user.id, db)
    return {"status": "deleted"}


@router.post("/configs/{config_id}/test")
async def test_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    from app.mcp.client import MCPClient

    configs = await MCPService.get_user_configs(current_user.id, db)
    config = next((c for c in configs if c.id == config_id), None)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        client = MCPClient(config)
        await client.connect()
        tool_count = len(client._tools)
        await client.disconnect()
        return {"status": "connected", "tool_count": tool_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/configs/{config_id}/tools", response_model=List[MCPToolResponse])
async def list_tools(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    configs = await MCPService.get_user_configs(current_user.id, db)
    config = next((c for c in configs if c.id == config_id), None)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        client = await MCPSessionManager.get_or_create_session(current_user.id, config)
        return [
            MCPToolResponse(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {},
            )
            for t in client._tools
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs/{config_id}/reload")
async def reload_config(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    configs = await MCPService.get_user_configs(current_user.id, db)
    config = next((c for c in configs if c.id == config_id), None)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await MCPSessionManager.reload_session(current_user.id, config.name)
    return {"status": "reloaded"}

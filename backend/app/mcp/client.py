import asyncio
import logging
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import create_model

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, config):
        self.config = config
        self.session = None
        self._tools = []
        self._cm = None
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.sse import sse_client

        transport = self.config.transport
        if transport == "stdio":
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args or [],
                env=self.config.env or {},
            )
            self._cm = stdio_client(server_params)
        elif transport == "sse":
            self._cm = sse_client(self.config.url)
        elif transport == "streamable":
            from mcp.client.streamable_http import streamablehttp_client
            self._cm = streamablehttp_client(self.config.url)
        else:
            raise ValueError(f"Unsupported transport: {transport}")

        try:
            entered = await asyncio.wait_for(self._cm.__aenter__(), timeout=10.0)
            # streamablehttp_client → (read, write, get_session_id) 3-tuple
            # stdio / sse → (read, write) 2-tuple
            read, write = entered[0], entered[1]
            self.session = ClientSession(read, write)
            await asyncio.wait_for(self.session.__aenter__(), timeout=10.0)

            await asyncio.wait_for(self.session.initialize(), timeout=10.0)
            result = await asyncio.wait_for(self.session.list_tools(), timeout=10.0)
            self._tools = result.tools
            self._connected = True
        except Exception as e:
            self._connected = False
            await self._safe_cleanup()
            raise RuntimeError(f"MCP connect failed: {e}") from e

    async def _safe_cleanup(self):
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        if self._cm:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._cm = None

    async def disconnect(self):
        self._connected = False
        await self._safe_cleanup()

    async def call_tool(self, name: str, arguments: dict) -> str:
        from mcp.types import TextContent

        if not self.session or not self._connected:
            logger.warning("[mcp] call_tool 실패: 세션 없음 tool=%s", name)
            return f"[MCP Error] Session not connected. Tool '{name}' could not be called."
        try:
            result = await asyncio.wait_for(
                self.session.call_tool(name, arguments), timeout=30.0
            )
            outputs = []
            for content in result.content:
                if isinstance(content, TextContent):
                    outputs.append(content.text)
            return "\n".join(outputs)
        except Exception as e:
            self._connected = False
            logger.warning("[mcp] call_tool 실패: tool=%s error=%s", name, e)
            return f"[MCP Error] Tool '{name}' call failed: {e}. The MCP server may have disconnected."

    def to_langchain_tools(self) -> list[StructuredTool]:
        lc_tools = []
        for tool in self._tools:
            tool_name = f"mcp_{self.config.name}_{tool.name}".replace("-", "_")
            input_schema = tool.inputSchema or {}
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])

            fields = {}
            for prop_name, prop_info in properties.items():
                field_type = self._json_type_to_python(prop_info.get("type", "string"))
                if prop_name in required:
                    fields[prop_name] = (field_type, ...)
                else:
                    fields[prop_name] = (Optional[field_type], None)

            ArgsSchema = create_model(f"{tool_name}_args", **fields) if fields else None

            def make_func(t_name: str):
                async def _call(**kwargs) -> str:
                    return await self.call_tool(t_name, kwargs)
                return _call

            kwargs = dict(
                name=tool_name,
                description=tool.description or f"MCP tool: {tool.name}",
                coroutine=make_func(tool.name),
            )
            if ArgsSchema:
                kwargs["args_schema"] = ArgsSchema

            lc_tools.append(StructuredTool(**kwargs))
        return lc_tools

    @staticmethod
    def _json_type_to_python(json_type: str) -> type:
        return {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }.get(json_type, str)

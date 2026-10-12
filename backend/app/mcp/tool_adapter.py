from typing import List

from langchain_core.tools import BaseTool

from app.mcp.client import MCPClient


def adapt_mcp_tools(client: MCPClient) -> List[BaseTool]:
    return client.to_langchain_tools()

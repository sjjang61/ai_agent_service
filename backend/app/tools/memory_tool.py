import json
from typing import Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

_memory_store: dict = {}


class MemoryInput(BaseModel):
    action: Literal["store", "retrieve", "list"] = Field(
        description="Action: store, retrieve, list"
    )
    key: Optional[str] = Field(default=None, description="Memory key")
    value: Optional[str] = Field(default=None, description="Value to store")


class MemoryTool(BaseTool):
    name: str = "memory_tool"
    description: str = (
        "Store and retrieve information for long-term memory. "
        "Use store to save info, retrieve to get it back by key."
    )
    args_schema: type[BaseModel] = MemoryInput
    user_id: str = ""

    def _run(self, action: str, key: str = None, value: str = None) -> str:
        ns = _memory_store.setdefault(self.user_id, {})
        if action == "store":
            ns[key] = value
            return f"Stored: {key}"
        elif action == "retrieve":
            return ns.get(key, f"Key '{key}' not found")
        elif action == "list":
            return json.dumps(list(ns.keys()))
        return "Unknown action"

    async def _arun(self, action: str, key: str = None, value: str = None) -> str:
        return self._run(action, key, value)

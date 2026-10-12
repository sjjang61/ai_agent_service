from typing import Any, Literal, Optional

from pydantic import BaseModel


class AgentStreamEvent(BaseModel):
    type: Literal["thought", "tool_call", "tool_result", "token", "done", "error"]
    content: Optional[str] = None
    tool: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[str] = None
    success: Optional[bool] = None
    message_id: Optional[str] = None
    message: Optional[str] = None

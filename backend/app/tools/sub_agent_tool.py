"""call_sub_agent: 리서치·코드 작성·파일 탐색 같은 하위 작업을 서브에이전트에 위임한다.

서브에이전트는 자신의 도구만 가지고 독립적으로 작업해 결과 텍스트만 돌려준다 (중간 과정은 호출한 쪽의 컨텍스트에 쌓이지 않는다).
서브에이전트는 call_sub_agent 를 갖지 않으므로 재귀 위임은 일어나지 않는다.
"""
import asyncio
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import render

SUB_AGENT_TIMEOUT = 300


class CallSubAgentInput(BaseModel):
    agent_type: Literal["research", "coder", "explorer"] = Field(
        description=(
            "research: web search/crawling and fact gathering; "
            "coder: write/run code and manage files in the sandbox; "
            "explorer: read-only exploration of workspace files (list, search, read)"
        )
    )
    task: str = Field(description="Self-contained task description. The sub-agent does not see the conversation")
    context: Optional[str] = Field(default=None, description="Extra background the sub-agent needs (paths, constraints, prior results)")


class CallSubAgentTool(BaseTool):
    name: str = "call_sub_agent"
    description: str = (
        "Delegate a self-contained sub-task to a specialist sub-agent (research / coder / explorer) and get back its final result. "
        "Use it for work that needs many tool calls (searching several sources, writing and testing code, scanning many files) "
        "so the details stay out of your context. Write the task so it is understandable without the conversation."
    )
    args_schema: type[BaseModel] = CallSubAgentInput
    # 서브에이전트가 쓸 수 있는 도구 후보 (call_sub_agent 자신은 제외하고 전달된다)
    tools: List[Any] = []
    llm_provider: str = ""
    model: Optional[str] = None

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    async def _arun(self, agent_type: str, task: str, context: Optional[str] = None) -> str:
        try:
            from app.agent.agno_engine import make_agent

            agent = make_agent(agent_type, self.tools, self.llm_provider, self.model)
            if agent is None:
                return f"Error: '{agent_type}' sub-agent has no usable tools in this session"
            prompt = task if not context else render("sub_agent_task", task=task, context=context)
            out = await asyncio.wait_for(agent.arun(prompt), timeout=SUB_AGENT_TIMEOUT)
            text = str(getattr(out, "content", "") or "").strip()
            return text[:20000] if text else "(sub-agent returned no result)"
        except asyncio.TimeoutError:
            return f"Error: sub-agent timed out after {SUB_AGENT_TIMEOUT}s"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

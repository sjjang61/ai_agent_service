from typing import AsyncIterator, List

from langchain_core.tools import BaseTool

from app.agent.memory import ConversationMemory
from app.agent.react_agent import AgentRunner


class AgentStreamingHandler:
    def __init__(
        self,
        tools: List[BaseTool],
        llm_provider: str = None,
        model: str = None,
        system_prompt: str = None,
    ):
        self.runner = AgentRunner(
            tools=tools, llm_provider=llm_provider, model=model, system_prompt=system_prompt
        )
        self.agent = self.runner.build_executor()

    async def stream(
        self, user_input: str, memory: ConversationMemory
    ) -> AsyncIterator[dict]:
        chat_history = memory.get_messages()
        async for event in self.runner.astream_events(
            self.agent, user_input, chat_history
        ):
            yield event

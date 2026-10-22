import logging
from typing import AsyncIterator, List, Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool

from app.config import normalize_llm_type, settings

logger = logging.getLogger(__name__)


class AgentRunner:
    """LangGraph create_react_agent 기반 Agent 실행기."""

    def __init__(
        self,
        tools: List[BaseTool],
        llm_provider: str = None,
        model: str = None,
        max_iterations: int = None,
        system_prompt: str = None,
    ):
        self.system_prompt = system_prompt
        self.llm_provider = normalize_llm_type(llm_provider or settings.LLM_TYPE)
        self.model = model or settings.default_model_for(self.llm_provider)
        self.tools = tools
        self.max_iterations = max_iterations or settings.AGENT_MAX_ITERATIONS
        self.llm = self._build_llm()

    def _build_llm(self):
        t = self.llm_provider
        if t == "pet":
            from langchain_openai import ChatOpenAI
            if not settings.PET_AGENT_URL:
                raise ValueError("PET_AGENT_URL이 설정되지 않았습니다.")
            return ChatOpenAI(
                model=settings.PET_MODEL_ID,
                base_url=settings.PET_AGENT_URL,
                api_key=settings.PET_API_KEY,
                streaming=False,
                timeout=settings.PET_TIMEOUT,
                reasoning_effort=settings.PET_REASONING_EFFORT or None,
            )
        if t == "openai":
            from langchain_openai import ChatOpenAI
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
            return ChatOpenAI(
                model=self.model,
                streaming=True,
                api_key=settings.OPENAI_API_KEY,
                reasoning_effort=settings.OPENAI_REASONING_EFFORT or None,
            )
        if t == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다.")
            return ChatGoogleGenerativeAI(
                model=self.model,
                streaming=True,
                google_api_key=settings.GOOGLE_API_KEY,
            )
        if t == "anthropic":
            from langchain_anthropic import ChatAnthropic
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
            return ChatAnthropic(
                model=self.model,
                streaming=True,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
            )
        raise ValueError(f"Unknown LLM_TYPE: {self.llm_provider} (pet | openai | gemini | anthropic)")

    def build_executor(self) -> Any:
        """LangGraph CompiledStateGraph 반환."""
        from langgraph.prebuilt import create_react_agent
        return create_react_agent(self.llm, self.tools, prompt=self.system_prompt)

    async def astream_events(
        self,
        agent: Any,
        user_input: str,
        chat_history: list,
    ) -> AsyncIterator[dict]:
        """
        LangGraph astream_events로 실시간 이벤트를 생성한다.

        - on_chat_model_stream → token
        - on_tool_start / on_tool_end → tool_call / tool_result
        - 스트리밍 없는 LLM → ainvoke 폴백
        - 모든 실패 → error 이벤트 yield
        """
        from app.agent.scope import with_scope_reminder

        messages = list(chat_history) + [HumanMessage(content=with_scope_reminder(user_input, bool(chat_history)))]
        token_yielded = False
        stream_error: Exception | None = None

        try:
            async for event in agent.astream_events(
                {"messages": messages},
                version="v2",
            ):
                event_name = event.get("event", "")
                event_data = event.get("data", {})

                if event_name == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content
                        if isinstance(content, str) and content:
                            token_yielded = True
                            yield {"type": "token", "content": content}

                elif event_name == "on_tool_start":
                    yield {
                        "type": "tool_call",
                        "tool": event.get("name", ""),
                        "input": event_data.get("input", {}),
                    }

                elif event_name == "on_tool_end":
                    output = str(event_data.get("output", ""))
                    yield {
                        "type": "tool_result",
                        "tool": event.get("name", ""),
                        "output": output,
                        "success": not output.startswith("[MCP Error]"),
                    }

        except Exception as e:
            logger.warning("[react_agent] astream_events 실패: %s", e)
            stream_error = e
            token_yielded = False

        # 스트리밍에서 토큰이 나오지 않은 경우 ainvoke 폴백
        if not token_yielded:
            logger.info("[react_agent] 스트리밍 토큰 없음 → ainvoke 폴백 실행")
            try:
                result = await agent.ainvoke({"messages": messages})
                for msg in reversed(result.get("messages", [])):
                    if (
                        hasattr(msg, "content")
                        and msg.content
                        and isinstance(msg.content, str)
                        and not getattr(msg, "tool_calls", None)
                    ):
                        yield {"type": "token", "content": msg.content}
                        token_yielded = True
                        break
            except Exception as e:
                logger.error("[react_agent] ainvoke 폴백 실패: %s", e)
                # ainvoke도 실패한 경우 error 이벤트 yield
                yield {
                    "type": "error",
                    "message": str(stream_error or e),
                }

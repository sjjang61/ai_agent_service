from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.config import settings


class ConversationMemory:
    def __init__(self, window: int = None):
        self.window = window or settings.AGENT_MEMORY_WINDOW
        self._messages: List[BaseMessage] = []

    def add_user_message(self, content: str):
        self._messages.append(HumanMessage(content=content))
        self._trim()

    def add_ai_message(self, content: str):
        self._messages.append(AIMessage(content=content))
        self._trim()

    def _trim(self):
        if len(self._messages) > self.window * 2:
            self._messages = self._messages[-(self.window * 2):]

    def get_messages(self) -> List[BaseMessage]:
        return self._messages

    def to_list(self) -> list:
        return [
            {
                "role": "user" if isinstance(m, HumanMessage) else "assistant",
                "content": m.content,
            }
            for m in self._messages
        ]

    @classmethod
    def from_db_messages(cls, db_messages: list) -> "ConversationMemory":
        mem = cls()
        for m in db_messages[-20:]:
            if m.role == "user":
                mem._messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                mem._messages.append(AIMessage(content=m.content))
        return mem

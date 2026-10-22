from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.config import settings


# 에이전트에게 원문 그대로 전달하는 최근 메시지 수. 이보다 오래된 메시지는 롤링 요약으로 대신한다.
HISTORY_WINDOW = 20


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
        from app.services.attachment_service import compose_with_attachments
        from app.services.reference_service import compose_with_references, reference_note

        mem = cls()
        window = db_messages[-HISTORY_WINDOW:]
        for i, m in enumerate(window):
            if m.role == "user":
                meta = getattr(m, "metadata_", None) or {}
                text = compose_with_attachments(m.content, meta.get("attachments"))
                refs = meta.get("references")
                if refs:
                    # 지금 처리 중인 마지막 메시지에는 참조 본문을 전부 싣고, 지난 메시지에는 제목만 남긴다.
                    if i == len(window) - 1:
                        text = compose_with_references(text, refs)
                    else:
                        text = f"{text}\n\n{reference_note(refs)}"
                mem._messages.append(HumanMessage(content=text))
            elif m.role == "assistant":
                mem._messages.append(AIMessage(content=m.content))
        return mem

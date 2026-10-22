"""작업 관리·사용자 상호작용 도구: todo / narrate / form_ask_user"""
import json
from collections import OrderedDict
from typing import Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import load

from app.core.forms import PendingForms, normalize_questions

FORM_TIMEOUT_SECONDS = 600
_STATUSES = ("pending", "in_progress", "completed")
_MAX_TODOS = 30
_MAX_CONVERSATIONS = 200
# conversation_id -> todos (프로세스 메모리, 오래된 대화부터 제거)
_todo_store: "OrderedDict[str, list[dict]]" = OrderedDict()


def complete_all_todos(conversation_id: str) -> None:
    """
    새 사용자 요청 시작 시 이전 작업의 미완료 todo를 모두 completed로 변경한다.
    이전 대화 컨텍스트가 에이전트에게 전달되더라도, 이전 작업을 다시 수행하지 않도록 한다.
    """
    import logging
    logger = logging.getLogger(__name__)

    key = conversation_id or "_"
    current = _todo_store.get(key, [])

    print(f"\n[COMPLETE_ALL_TODOS] Called for conversation: {conversation_id[:16]}...")
    print(f"  Current todos in store: {len(current)}")

    if not current:
        print(f"  -> No todos found, skipping")
        return

    incomplete_count = sum(1 for todo in current if todo["status"] != "completed")
    print(f"  Incomplete todos: {incomplete_count}")

    if incomplete_count > 0:
        print(f"  -> Marking {incomplete_count} todos as completed:")
        for todo in current:
            if todo["status"] != "completed":
                print(f"     - [{todo['id']}] {todo['content'][:60]} ... ({todo['status']} -> completed)")
                todo["status"] = "completed"

        _todo_store[key] = current
        _todo_store.move_to_end(key)
        logger.info(f"[todo] 새 요청 시작 - {incomplete_count}개의 미완료 todo를 자동 완료 처리 (conversation: {conversation_id[:8]}...)")
    else:
        print(f"  -> All todos already completed, no action needed")


class _Base(BaseTool):
    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"


# ── todo ─────────────────────────────────────────────────────────────────────
class TodoInput(BaseModel):
    action: Literal["write", "update", "read"] = Field(
        default="write",
        description="write: replace the whole list with `todos`; update: change one item's status by `id`; read: return the current list",
    )
    todos: Optional[list[dict]] = Field(
        default=None,
        description='For write: full list of {"content": "short step", "status": "pending|in_progress|completed"} (id optional, auto-numbered)',
    )
    id: Optional[str] = Field(default=None, description="For update: the todo id")
    status: Optional[Literal["pending", "in_progress", "completed"]] = Field(default=None, description="For update: new status")


class TodoTool(_Base):
    name: str = "todo"
    description: str = (
        "Plan and track a multi-step task. At the start of work with 3+ steps, call write with the full plan; "
        "then update each item's status as you go (mark exactly one item in_progress, mark it completed right when done). "
        "The list is shown to the user as a checklist. Skip it for trivial single-step requests."
    )
    args_schema: type[BaseModel] = TodoInput
    conversation_id: str = ""

    async def _arun(self, action: str = "write", todos: Optional[list] = None,
                    id: Optional[str] = None, status: Optional[str] = None) -> str:
        key = self.conversation_id or "_"
        current = _todo_store.get(key, [])
        if action == "write":
            if not todos or len(todos) > _MAX_TODOS:
                return f"Error: todos must contain 1-{_MAX_TODOS} items"
            items = []
            for i, t in enumerate(todos):
                content = str((t or {}).get("content", "")).strip()[:200]
                st = (t or {}).get("status", "pending")
                if not content or st not in _STATUSES:
                    return f"Error: todos[{i}] needs non-empty content and status in {_STATUSES}"
                items.append({"id": str((t or {}).get("id") or i + 1)[:20], "content": content, "status": st})
            if len({x["id"] for x in items}) != len(items):
                return "Error: todo ids must be unique"
            current = items
        elif action == "update":
            target = next((x for x in current if x["id"] == str(id)), None)
            if not target or status not in _STATUSES:
                ids = ", ".join(x["id"] for x in current) or "(empty)"
                return f"Error: update needs an existing id (current ids: {ids}) and a valid status"
            target["status"] = status
        _todo_store[key] = current
        _todo_store.move_to_end(key)
        while len(_todo_store) > _MAX_CONVERSATIONS:
            _todo_store.popitem(last=False)

        done = sum(1 for x in current if x["status"] == "completed")
        nxt = next((x for x in current if x["status"] == "in_progress"), None) or next(
            (x for x in current if x["status"] == "pending"), None
        )
        return json.dumps(
            {"ok": True, "todos": current, "progress": f"{done}/{len(current)}",
             "next": nxt["content"] if nxt else None},
            ensure_ascii=False,
        )


# ── narrate ──────────────────────────────────────────────────────────────────
class NarrateInput(BaseModel):
    message: str = Field(description="One short sentence telling the user what you are doing or about to do (max ~120 chars)")


class NarrateTool(_Base):
    name: str = "narrate"
    description: str = (
        "Tell the user a short progress note (one sentence) before or during long, multi-step work, "
        "e.g. '관련 자료를 검색하고 있습니다'. Do not narrate every tool call and do not use it for the final answer."
    )
    args_schema: type[BaseModel] = NarrateInput

    async def _arun(self, message: str) -> str:
        return "Shown to the user."


# ── form_ask_user ────────────────────────────────────────────────────────────
class FormAskUserInput(BaseModel):
    title: str = Field(description="Short form title, e.g. '여행 조건 확인'")
    questions: list[dict] = Field(
        description=(
            'Questions to ask (1-10). Each: {"id": "budget", "label": "예산은?", '
            '"type": "single_choice" | "multi_choice" | "text", '
            '"options": ["...", "..."] (2-12, required for choice types), '
            '"allow_other": true to also accept free text for choice types, '
            '"placeholder": optional hint for text, "required": true by default}'
        )
    )
    description: Optional[str] = Field(default=None, description="Optional one-line explanation shown under the title")


class FormAskUserTool(_Base):
    name: str = "form_ask_user"
    description: str = (
        "Ask the user to choose among options or type a free-form answer, shown as a form in the chat. "
        "Execution PAUSES until the user submits (or cancels, or 10 minutes pass). Use it when you need a decision or missing "
        "information that you cannot reasonably guess; ask everything in one form instead of several. "
        "Returns JSON: {\"answers\": {question_id: value}} or {\"cancelled\": true} / {\"timeout\": true}."
    )
    args_schema: type[BaseModel] = FormAskUserInput
    user_id: str = ""
    conversation_id: str = ""

    async def _arun(self, title: str, questions: list, description: Optional[str] = None) -> str:
        try:
            qs = normalize_questions(questions)
        except ValueError as e:
            return f"Error: invalid form - {e}. Fix the questions and call form_ask_user again."
        result = await PendingForms.ask(self.conversation_id, self.user_id, qs, FORM_TIMEOUT_SECONDS)
        return json.dumps(result, ensure_ascii=False)


class HeadlessAskUserTool(_Base):
    """예약 실행처럼 사용자가 없을 때 form_ask_user 를 대신한다 (응답을 기다리며 멈추지 않는다)."""

    name: str = "form_ask_user"
    description: str = (
        "Unavailable in this unattended (scheduled) run: there is no user to answer. "
        "Do not rely on it; make reasonable assumptions and state them in the final report."
    )
    args_schema: type[BaseModel] = FormAskUserInput

    async def _arun(self, title: str = "", questions: Optional[list] = None, description: Optional[str] = None) -> str:
        return json.dumps(
            {
                "unavailable": True,
                "message": load("tool_result_headless_ask"),
            },
            ensure_ascii=False,
        )

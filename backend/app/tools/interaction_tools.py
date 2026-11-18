"""작업 관리·사용자 상호작용 도구: todo / narrate / form_ask_user"""
import uuid
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


def _todo_result(current: list) -> str:
    """todo 도구가 돌려주는 JSON (화면의 작업 계획이 이 형식을 읽는다)."""
    done = sum(1 for x in current if x["status"] == "completed")
    nxt = next((x for x in current if x["status"] == "in_progress"), None) or next(
        (x for x in current if x["status"] == "pending"), None
    )
    return json.dumps(
        {"ok": True, "todos": current, "progress": f"{done}/{len(current)}", "next": nxt["content"] if nxt else None},
        ensure_ascii=False,
    )


def plan_review_note(conversation_id: str) -> str:
    """작업(위임·브라우저 등)이 끝난 직후 도구 결과 뒤에 붙이는 계획 점검 안내. 끝나지 않은 단계가 있을 때만 (없으면 빈 문자열).
    모델이 방금 끝난 작업으로 이미 처리된 단계를 놓치고 같은 일을 다시 맡기거나 계획 갱신을 건너뛰는 것을 막는다."""
    current = _todo_store.get(conversation_id or "_") or []
    if not current or all(x["status"] == "completed" for x in current):
        return ""
    mark = {"completed": "완료", "in_progress": "진행 중", "pending": "대기"}
    rows = "\n".join(f"  {x['id']}. {x['content']} [{mark.get(x['status'], x['status'])}]" for x in current)
    return (
        "\n\n[계획 점검] 방금 끝난 작업을 계획과 대조하세요. 현재 계획:\n" + rows + "\n"
        "- 이 작업으로 이미 처리된 단계가 있으면(예: 한 번의 위임이 여러 단계를 다 했을 때) 그 단계들을 `todo` 로 completed 처리하고, 남은 단계가 있으면 다음 단계를 `start` 하세요.\n"
        "- 같은 일을 하는 단계가 둘로 나뉘어 있으면 `todo` 의 write 로 합쳐 다시 쓰세요(끝낸 단계는 completed 로 둡니다).\n"
        "- 이미 끝난 일을 같은 방식으로 다시 위임하지 마세요. 남은 단계가 없으면 `todo` 를 갱신한 뒤 최종 답변을 하세요."
    )


def seed_todos(conversation_id: str, steps: list) -> tuple:
    """요청 라우터가 만든 전체 작업 계획을 todo 로 넣는다 (첫 단계는 진행 중). (todos, todo 도구 결과 JSON) 반환."""
    key = conversation_id or "_"
    items = [
        {"id": str(i + 1), "content": str(s).strip()[:200], "status": "in_progress" if i == 0 else "pending"}
        for i, s in enumerate(steps[:_MAX_TODOS])
    ]
    _todo_store[key] = items
    _todo_store.move_to_end(key)
    while len(_todo_store) > _MAX_CONVERSATIONS:
        _todo_store.popitem(last=False)
    return items, _todo_result(items)


def finish_plan(conversation_id: str) -> Optional[str]:
    """응답이 정상적으로 끝났는데 계획에 끝나지 않은 단계가 남아 있으면 모두 completed 로 바꾸고 todo 결과 JSON 을 돌려준다.
    (리더가 위임 뒤 계획을 갱신하지 않은 채 최종 답변을 낸 경우 화면의 계획이 1단계에 머무는 것을 막는다.) 남은 단계가 없으면 None."""
    key = conversation_id or "_"
    current = _todo_store.get(key)
    if not current or all(x["status"] == "completed" for x in current):
        return None
    for x in current:
        x["status"] = "completed"
    _todo_store.move_to_end(key)
    return _todo_result(current)


class _Base(BaseTool):
    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"


# ── todo ─────────────────────────────────────────────────────────────────────
class TodoInput(BaseModel):
    action: Literal["write", "update", "start", "read"] = Field(
        default="write",
        description="write: replace the whole list with `todos`; update: change one item's status by `id`; start: mark item `id` in_progress and complete the previous in_progress item; read: return the current list",
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
        elif action == "start":
            target = next((x for x in current if x["id"] == str(id)), None)
            if not target:
                ids = ", ".join(x["id"] for x in current) or "(empty)"
                return f"Error: start needs an existing id (current ids: {ids})"
            for x in current:
                if x["status"] == "in_progress" and x is not target:
                    x["status"] = "completed"
            target["status"] = "in_progress"
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

        result = _todo_result(current)
        if action in ("write", "start", "update"):
            self._emit_plan_hint(result)
        return result

    def _emit_plan_hint(self, result: str) -> None:
        """계획 상태가 바뀐 순간 화면 스트림에 바로 알린다.
        한 응답에서 `start` 와 긴 작업 도구(브라우저 등)를 병렬로 호출하면 Agno 의 호출·결과 이벤트는 그 작업이 끝난 뒤에야 도착해서,
        작업 중 화면이 새 단계를 모르고 이전 단계 아래에 진행 상황을 묶어 보여 준다. todo 는 몇 ms 만에 끝나므로 여기서 먼저 알려 순서를 맞춘다.
        call_id 가 plan_hint_ 로 시작하는 이 결과는 목록에는 나타나지 않고(호출과 짝짓지 않는다), 계획 상태 계산에만 쓰인다."""
        from app.agent import side_events

        side_events.emit(self.conversation_id, {"type": "tool_result", "tool": "todo", "output": result,
                                                "call_id": f"plan_hint_{uuid.uuid4().hex[:8]}", "success": True})


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


class ChatAskUserTool(_Base):
    """메신저 대화: 폼을 띄울 수 없으므로 일반 문장으로 되묻게 한다."""

    name: str = "form_ask_user"
    description: str = (
        "Unavailable in this messenger chat (no form UI). Ask your question as plain text at the end of your "
        "final answer and wait for the user's next message."
    )
    args_schema: type[BaseModel] = FormAskUserInput

    async def _arun(self, title: str = "", questions: Optional[list] = None, description: Optional[str] = None) -> str:
        return json.dumps(
            {"unavailable": True, "message": "Forms are not available here. Ask the question in plain text in your reply, then stop and wait."},
            ensure_ascii=False,
        )

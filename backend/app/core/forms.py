"""form_ask_user 가 사용하는 '사용자 응답 대기' 레지스트리.

에이전트 실행(SSE/WS 스트림)은 도구 안에서 사용자의 응답을 기다리고, 프론트엔드는 별도의 REST 호출
(POST /api/chat/conversations/{id}/form-answer)로 응답을 전달한다. 대화(conversation)당 동시에 하나의 폼만 대기한다.
단일 프로세스(in-memory) 기준이며, 다중 프로세스 배포에서는 Redis 등으로 바꿔야 한다.
"""
import asyncio
from typing import Any, Optional

VALID_TYPES = ("single_choice", "multi_choice", "text")


def normalize_questions(raw: Any) -> list[dict]:
    """LLM 이 만든 questions 를 검증·정규화한다. 문제가 있으면 ValueError."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= 10:
        raise ValueError("questions 는 1~10개의 배열이어야 합니다")
    out, seen = [], set()
    for i, q in enumerate(raw):
        if not isinstance(q, dict):
            raise ValueError(f"questions[{i}] 는 객체여야 합니다")
        qid = str(q.get("id") or f"q{i + 1}").strip()[:40]
        if qid in seen:
            raise ValueError(f"질문 id 가 중복되었습니다: {qid}")
        seen.add(qid)
        qtype = q.get("type", "text")
        if qtype not in VALID_TYPES:
            raise ValueError(f"questions[{i}].type 은 {', '.join(VALID_TYPES)} 중 하나여야 합니다")
        label = str(q.get("label") or "").strip()[:300]
        if not label:
            raise ValueError(f"questions[{i}].label 이 비어 있습니다")
        item: dict[str, Any] = {
            "id": qid, "type": qtype, "label": label,
            "required": bool(q.get("required", True)),
        }
        if qtype in ("single_choice", "multi_choice"):
            opts = [str(o).strip()[:200] for o in (q.get("options") or []) if str(o).strip()]
            if not 2 <= len(opts) <= 12:
                raise ValueError(f"questions[{i}].options 는 2~12개의 문자열이어야 합니다")
            item["options"] = opts
            item["allow_other"] = bool(q.get("allow_other", False))
        else:
            if q.get("placeholder"):
                item["placeholder"] = str(q["placeholder"])[:200]
        out.append(item)
    return out


def validate_answers(questions: list[dict], answers: dict) -> dict:
    """사용자 응답을 질문 정의에 맞게 검증·정리한다. 문제가 있으면 ValueError."""
    clean: dict[str, Any] = {}
    for q in questions:
        v = answers.get(q["id"])
        empty = v is None or v == "" or v == []
        if empty:
            if q["required"]:
                raise ValueError(f"'{q['label']}' 에 응답이 필요합니다")
            continue
        if q["type"] == "text":
            clean[q["id"]] = str(v)[:5000]
        elif q["type"] == "single_choice":
            v = str(v)
            if v not in q["options"] and not q["allow_other"]:
                raise ValueError(f"'{q['label']}' 의 선택지가 올바르지 않습니다")
            clean[q["id"]] = v[:500]
        else:
            vals = [str(x) for x in (v if isinstance(v, list) else [v])]
            if not q["allow_other"] and any(x not in q["options"] for x in vals):
                raise ValueError(f"'{q['label']}' 의 선택지가 올바르지 않습니다")
            clean[q["id"]] = [x[:500] for x in vals[:20]]
    return clean


class _Pending:
    def __init__(self, user_id: str, questions: list[dict], future: asyncio.Future):
        self.user_id, self.questions, self.future = user_id, questions, future


class PendingForms:
    _pending: dict[str, _Pending] = {}

    @classmethod
    async def ask(cls, conversation_id: str, user_id: str, questions: list[dict], timeout: float) -> dict:
        """폼을 등록하고 응답을 기다린다. 반환: {"answers": {...}} | {"cancelled": True} | {"timeout": True}"""
        old = cls._pending.pop(conversation_id, None)
        if old and not old.future.done():
            old.future.set_result({"cancelled": True})
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        cls._pending[conversation_id] = _Pending(user_id, questions, fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return {"timeout": True}
        finally:
            cur = cls._pending.get(conversation_id)
            if cur and cur.future is fut:
                cls._pending.pop(conversation_id, None)

    @classmethod
    def answer(cls, conversation_id: str, user_id: str, answers: Optional[dict], cancelled: bool = False) -> bool:
        """응답 전달. 대기 중인 폼이 없으면 False. 응답이 유효하지 않으면 ValueError."""
        p = cls._pending.get(conversation_id)
        if not p or p.user_id != user_id or p.future.done():
            return False
        if cancelled:
            p.future.set_result({"cancelled": True})
        else:
            p.future.set_result({"answers": validate_answers(p.questions, answers or {})})
        return True

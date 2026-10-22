"""manage_schedule: 채팅에서 예약 작업을 만들고 조회·수정·일시중지·재개·삭제한다.

사용자가 "매일 아침 9시에 AI 뉴스 요약해줘" 처럼 말하면 에이전트가 이 도구로 예약을 등록한다.
예약 화면(/schedules)에서 만든 것과 같은 서비스(ScheduleService)를 쓰므로 한도·검증·다음 실행 계산이 동일하다.

안전장치
- 예약 실행(headless) 안에서는 등록하지 않는다 (예약이 예약을 만드는 연쇄 방지 — 오케스트레이터가 도구를 넣지 않음)
- MCP·브라우저 에이전트 허용은 이 도구로 켤 수 없다 (자동 실행의 권한 상승 방지 — 예약 화면에서 사용자가 직접 설정)
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from langchain_core.tools import BaseTool

from app.agent.prompts import load

from app.config import settings
from app.schemas.schedule import TaskInput, TaskUpdate
from app.services import schedule_calc as calc
from app.services.schedule_service import ScheduleService, now_utc

_DAYS = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def parse_weekdays(text: Optional[str]) -> Optional[list[int]]:
    """'월,금' / 'mon, fri' / '0,4' → [0, 4]. 해석할 수 없는 토큰이 있으면 ValueError."""
    if text is None:
        return None
    out: list[int] = []
    for tok in re.split(r"[,\s·/]+", str(text).strip().lower()):
        if not tok:
            continue
        tok = tok.removesuffix("요일").removesuffix("요")
        if tok in _DAYS:
            out.append(_DAYS[tok])
        elif tok.isdigit() and 0 <= int(tok) <= 6:
            out.append(int(tok))
        else:
            raise ValueError(f"알 수 없는 요일입니다: '{tok}' (예: 월,금)")
    return sorted(set(out))


def parse_local_datetime(text: str, tz_name: str) -> datetime:
    """'2026-10-20 09:30' (현지 시각) → UTC naive datetime."""
    try:
        dt = datetime.fromisoformat(text.strip().replace("T", " "))
    except ValueError:
        raise ValueError("run_at 은 'YYYY-MM-DD HH:MM' 형식이어야 합니다")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=calc.get_tz(tz_name))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


class ManageScheduleInput(BaseModel):
    action: Literal["create", "list", "update", "pause", "resume", "delete"] = Field(
        description="create: register a new scheduled task; list: show the user's tasks; update/pause/resume/delete: manage an existing one"
    )
    task: Optional[str] = Field(
        default=None,
        description="For update/pause/resume/delete: the task id or its name. For pause/resume/delete use 'all' to apply to every task (only when the user explicitly asked for all)",
    )
    name: Optional[str] = Field(default=None, description="Short task name, e.g. '아침 뉴스 브리핑' (create)")
    prompt: Optional[str] = Field(
        default=None,
        description="What the agent must do on each run. Write it self-contained: it runs later WITHOUT this conversation, so include all needed details (create/update)",
    )
    schedule_type: Optional[Literal["once", "interval", "daily", "weekdays", "weekly", "monthly"]] = Field(
        default=None, description="once | interval (every N hours) | daily | weekdays (Mon-Fri) | weekly | monthly"
    )
    time: Optional[str] = Field(default=None, description="Local time 'HH:MM' (24h) for daily/weekdays/weekly/monthly")
    weekdays: Optional[str] = Field(default=None, description="For weekly: comma-separated days, e.g. '월,금' or 'mon,fri'")
    day_of_month: Optional[int] = Field(default=None, description="For monthly: 1-31 (short months use the last day)")
    interval_hours: Optional[int] = Field(default=None, description="For interval: every N hours (minimum 1)")
    run_at: Optional[str] = Field(default=None, description="For once: local date-time 'YYYY-MM-DD HH:MM' in `timezone`")
    in_minutes: Optional[int] = Field(default=None, description="For once: run N minutes from now (alternative to run_at)")
    timezone: Optional[str] = Field(default=None, description="IANA timezone like 'Asia/Seoul'. Omit to use the user's timezone")
    request_quote: Optional[str] = Field(
        default=None,
        description=(
            "REQUIRED for create/update/pause/resume/delete: copy a short phrase (3+ characters) VERBATIM from the user's LATEST message "
            "that asks for this action. Requests from earlier turns were already handled - never repeat them; calls whose quote is not "
            "in the latest message are rejected."
        ),
    )


class ManageScheduleTool(BaseTool):
    name: str = "manage_schedule"
    description: str = (
        "Create and manage the user's scheduled tasks (recurring or one-time jobs the agent runs automatically later, "
        "like 'every day at 9am summarize AI news'). Use create ONLY when the user asks to schedule/repeat something. "
        "If what to do or when is unclear, ask first. To CHANGE an existing schedule (user says 바꿔줘/수정/변경/'그 예약' …) "
        "use action=update on it - never create a new one for a change request; call list first if you are unsure which one. Scheduled runs have no user present and cannot use MCP tools or the "
        "browser agent unless the user enables them in the Schedules screen. Actions: create, list, update, pause, resume, delete."
    )
    args_schema: type[BaseModel] = ManageScheduleInput
    user_id: str = ""
    default_timezone: str = ""
    current_message: str = ""  # 이번 턴의 사용자 메시지 (과거 요청의 재실행을 막는 데 쓴다)

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"

    # ── helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _brief(resp) -> dict:
        return {
            "id": resp.id, "name": resp.name, "schedule_text": resp.schedule_text, "status": resp.status,
            "next_run_at": resp.next_run_at.isoformat() if resp.next_run_at else None, "timezone": resp.timezone,
        }

    async def _resolve(self, ref: Optional[str], db):
        tasks = await ScheduleService.list_tasks(self.user_id, db)
        if not ref:
            raise ValueError("task(예약 id 또는 이름)를 지정하세요")
        for t in tasks:
            if t.id == ref:
                return t
        low = ref.strip().lower()
        exact = [t for t in tasks if t.name.lower() == low]
        found = exact or [t for t in tasks if low in t.name.lower()]
        if len(found) == 1:
            return found[0]
        if not found:
            names = ", ".join(f"'{t.name}'" for t in tasks) or "(없음)"
            raise ValueError(f"'{ref}' 예약을 찾을 수 없습니다. 현재 예약: {names}")
        raise ValueError("이름이 겹치는 예약이 여러 개입니다: " + ", ".join(f"'{t.name}'({t.id[:8]})" for t in found))

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"[\s\W_]+", "", text or "").lower()

    def _check_quote(self, quote: Optional[str]) -> Optional[str]:
        """부작용이 있는 호출이 '이번 턴의 사용자 요청'에서 나온 것인지 확인한다. 아니면 오류 문장을 돌려준다.

        모델이 대화 기록의 이전 요청(이미 처리됨)을 다시 실행하는 일이 있어, 마지막 사용자 메시지에서 그대로 인용한 문구를 요구한다.
        """
        if not self.current_message:
            return None  # 현재 메시지를 모르는 호출(테스트 등)은 검증하지 않는다
        q = self._norm(quote or "")
        if len(q) < 3:
            return load("tool_error_quote_missing")
        if q not in self._norm(self.current_message):
            return load("tool_error_quote_mismatch")
        return None

    async def _find_duplicate(self, db, name, prompt, schedule_type, time, weekdays, day_of_month, interval_hours, tz):
        """같은 이름의 예약, 또는 최근 10분 안에 만든 같은 일정의 예약이 있으면 그 예약을 돌려준다."""
        norm = re.sub(r"\s+", "", name or "").lower()
        recent = now_utc() - timedelta(minutes=10)
        for t in await ScheduleService.list_tasks(self.user_id, db):
            if t.schedule_type == "once" and t.next_run_at is None:
                continue  # 이미 실행이 끝난 한 번 실행 작업은 중복으로 보지 않는다
            if re.sub(r"\s+", "", t.name).lower() == norm:
                return t
            if prompt and t.created_at is not None and t.created_at >= recent and self._norm(t.prompt) == self._norm(prompt):
                return t  # 이름만 바꿔 같은 요청을 다시 등록하는 경우
            same_schedule = (
                t.schedule_type == schedule_type and t.schedule_type != "once" and t.schedule_time == time
                and (t.weekdays or None) == (weekdays or None) and t.day_of_month == day_of_month
                and t.interval_hours == interval_hours and t.timezone == tz
            )
            if same_schedule and t.created_at is not None and t.created_at >= recent:
                return t
        return None

    def _tz(self, tz: Optional[str]) -> str:
        name = tz or self.default_timezone or settings.SCHEDULER_DEFAULT_TIMEZONE
        calc.get_tz(name)  # 잘못된 시간대면 ScheduleError
        return name

    # ── 실행 ────────────────────────────────────────────────────────────────
    async def _arun(self, action: str, task: Optional[str] = None, name: Optional[str] = None, prompt: Optional[str] = None,
                    schedule_type: Optional[str] = None, time: Optional[str] = None, weekdays: Optional[str] = None,
                    day_of_month: Optional[int] = None, interval_hours: Optional[int] = None, run_at: Optional[str] = None,
                    in_minutes: Optional[int] = None, timezone: Optional[str] = None,
                    request_quote: Optional[str] = None) -> str:
        from app.db.session import AsyncSessionLocal

        if action != "list":
            rejected = self._check_quote(request_quote)
            if rejected:
                return rejected
        try:
            async with AsyncSessionLocal() as db:
                if action == "list":
                    resps = await ScheduleService.to_responses(await ScheduleService.list_tasks(self.user_id, db), db)
                    return json.dumps({"ok": True, "action": "list", "tasks": [self._brief(r) for r in resps]}, ensure_ascii=False)

                if action == "create":
                    if not (name and prompt and schedule_type):
                        return "Error: create 에는 name, prompt, schedule_type 이 필요합니다"
                    tz = self._tz(timezone)
                    if schedule_type == "once":
                        if in_minutes is not None:
                            run_utc = now_utc() + timedelta(minutes=in_minutes)
                        elif run_at:
                            run_utc = parse_local_datetime(run_at, tz)
                        else:
                            return "Error: once 에는 run_at 또는 in_minutes 가 필요합니다"
                    else:
                        run_utc = None
                    # 같은 요청이 반복 실행되어 예약이 중복 생성되는 것을 막는다 (대화 기록의 이전 요청을 다시 실행하는 경우 등)
                    dup = await self._find_duplicate(db, name, prompt, schedule_type, time, parse_weekdays(weekdays), day_of_month, interval_hours, tz)
                    if dup is not None:
                        return (f"Error: 같은 예약이 이미 있습니다: '{dup.name}' (id {dup.id}, {calc.describe(dup.schedule_type, schedule_time=dup.schedule_time, weekdays=dup.weekdays, day_of_month=dup.day_of_month, interval_hours=dup.interval_hours, timezone_name=dup.timezone)}). "
                                "새로 만들지 마세요. 내용을 바꾸려면 action=update 를 쓰고, 사용자가 정말 별도의 예약을 원하면 다른 이름으로 만드세요.")
                    data = TaskInput(
                        name=name, prompt=prompt, schedule_type=schedule_type, schedule_time=time,
                        weekdays=parse_weekdays(weekdays), day_of_month=day_of_month, interval_hours=interval_hours,
                        run_at=run_utc, timezone=tz,
                    )  # allow_mcp / allow_browser 는 기본값(False) — 이 도구로 켤 수 없다
                    t = await ScheduleService.create_task(self.user_id, data, db)
                    resp = (await ScheduleService.to_responses([t], db))[0]
                    return json.dumps({
                        "ok": True, "action": "create", "task": self._brief(resp),
                        "note": "예약되었습니다. MCP·브라우저 에이전트가 필요한 작업이면 예약 화면에서 허용을 켜야 합니다.",
                    }, ensure_ascii=False)

                if (task or "").strip().lower() in ("all", "*", "전부", "모두", "전체"):
                    if action not in ("pause", "resume", "delete"):
                        return "Error: 'all' 은 pause/resume/delete 에서만 쓸 수 있습니다"
                    done = []
                    for t in await ScheduleService.list_tasks(self.user_id, db):
                        brief = {"id": t.id, "name": t.name}
                        if action == "delete":
                            await ScheduleService.delete_task(t, db)
                        else:
                            try:
                                t = await ScheduleService.set_enabled(t, action == "resume", db)
                            except HTTPException:
                                continue  # 예: 이미 지난 한 번 실행 작업은 재개할 수 없다
                            brief = self._brief((await ScheduleService.to_responses([t], db))[0])
                        done.append(brief)
                    return json.dumps({"ok": True, "action": action, "tasks": done, "count": len(done)}, ensure_ascii=False)

                t = await self._resolve(task, db)
                if action == "pause":
                    t = await ScheduleService.set_enabled(t, False, db)
                elif action == "resume":
                    t = await ScheduleService.set_enabled(t, True, db)
                elif action == "update":
                    patch: dict = {}
                    if name: patch["name"] = name
                    if prompt: patch["prompt"] = prompt
                    if schedule_type: patch["schedule_type"] = schedule_type
                    if time: patch["schedule_time"] = time
                    if weekdays is not None: patch["weekdays"] = parse_weekdays(weekdays)
                    if day_of_month: patch["day_of_month"] = day_of_month
                    if interval_hours: patch["interval_hours"] = interval_hours
                    if timezone: patch["timezone"] = self._tz(timezone)
                    if in_minutes is not None:
                        patch["run_at"] = now_utc() + timedelta(minutes=in_minutes)
                    elif run_at:
                        patch["run_at"] = parse_local_datetime(run_at, patch.get("timezone") or t.timezone)
                    if not patch:
                        return "Error: 바꿀 항목(name, prompt, time 등)을 지정하세요"
                    t = await ScheduleService.update_task(t, TaskUpdate(**patch), db)
                elif action == "delete":
                    brief = {"id": t.id, "name": t.name}
                    await ScheduleService.delete_task(t, db)
                    return json.dumps({"ok": True, "action": "delete", "task": brief,
                                       "note": "삭제했습니다. 이미 만들어진 결과 대화는 남아 있습니다."}, ensure_ascii=False)
                else:
                    return f"Error: 알 수 없는 action '{action}'"
                resp = (await ScheduleService.to_responses([t], db))[0]
                return json.dumps({"ok": True, "action": action, "task": self._brief(resp)}, ensure_ascii=False)
        except HTTPException as e:
            return f"Error: {e.detail}"
        except (calc.ScheduleError, ValueError) as e:
            return f"Error: {e}"
        except ValidationError as e:
            return "Error: " + "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:3])

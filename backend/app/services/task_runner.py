"""예약 작업 한 회차를 사용자 없이 실행하고 결과를 대화·이력에 남긴다."""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import render
from app.config import settings
from app.core.runs import RunRegistry, cancellable_events
from app.models.conversation import Conversation
from app.models.scheduled_task import ScheduledTask, TaskRun
from app.schemas.chat import ConversationCreate
from app.services.chat_service import ChatService
from app.services.schedule_service import now_utc

logger = logging.getLogger(__name__)

CANCEL_NOTE = "_(사용자가 실행을 중단했습니다)_"
_background: set = set()  # create_task 결과를 붙잡아 GC 로 사라지지 않게 한다


def spawn(coro) -> "asyncio.Task":
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task


def _summarize(text: str, limit: int = 300) -> str:
    text = re.sub(r"[#*_`>\[\]]+", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


NO_ALERT = "[NO_ALERT]"
PREVIOUS_RESULT_MAX = 4000


def notify_rules(task: ScheduledTask) -> str:
    """알림 조건이 있는 예약이면 실행 지시에 붙일 알림 규칙. 없으면 빈 문자열."""
    mode = task.notify_mode or "always"
    if mode == "on_condition" and (task.notify_condition or "").strip():
        return render("scheduled_notify_condition", condition=task.notify_condition.strip())
    if mode == "on_change" and (task.last_result or "").strip():  # 첫 실행은 비교할 결과가 없으니 항상 알린다
        return render("scheduled_notify_change", previous=task.last_result[:PREVIOUS_RESULT_MAX])
    return ""


def split_no_alert(text: str) -> tuple[str, bool]:
    """답변 첫 줄이 [NO_ALERT] 면 (표시를 뗀 본문, True)."""
    lines = (text or "").lstrip().split("\n", 1)
    if lines and lines[0].strip().upper().startswith(NO_ALERT):
        rest = lines[0].strip()[len(NO_ALERT):].strip()
        body = "\n".join(x for x in (rest, lines[1].strip() if len(lines) > 1 else "") if x)
        return body or "알림 조건에 해당하지 않습니다", True
    return text, False


def maybe_suggest_followups(task: ScheduledTask, message_id: str, answer: str, status: str, no_alert: bool) -> bool:
    """성공한 실행의 결과 답변에 일반 채팅 답변처럼 이어서 물어볼 만한 질문 2개를 붙인다 (백그라운드로 만들어 메시지에 저장).
    사용자에게 보이지 않을 실행(조건에 해당하지 않아 알리지 않은 것)·실패·취소는 비용만 들어서 만들지 않는다. 붙이기를 시작했으면 True."""
    if status != "succeeded" or no_alert or not answer.strip() or not settings.ENABLE_FOLLOWUP_SUGGESTIONS:
        return False
    from app.services.followup_service import schedule_attach

    schedule_attach(message_id, task.prompt or "", answer)
    return True


def should_notify(task: ScheduledTask, status: str, no_alert: bool, trigger: str = "schedule") -> bool:
    """이번 실행 결과를 알림으로 올릴지. 실패는 방식과 무관하게 항상 알리고, 수동 실행은 사용자가 직접 본다."""
    if status != "succeeded" or trigger != "schedule":
        return True
    mode = task.notify_mode or "always"
    if mode == "on_failure":
        return False
    if mode in ("on_change", "on_condition"):
        return not no_alert
    return True


def _local_label(task: ScheduledTask, when: datetime, fmt: str) -> str:
    try:
        tz = ZoneInfo(task.timezone)
    except Exception:
        tz = timezone.utc
    return when.replace(tzinfo=timezone.utc).astimezone(tz).strftime(fmt)


async def has_active_run(task_id: str, db: AsyncSession) -> bool:
    r = await db.execute(
        select(TaskRun.id).where(TaskRun.task_id == task_id, TaskRun.status.in_(("queued", "running"))).limit(1)
    )
    return r.first() is not None


async def create_run(
    task: ScheduledTask, trigger: str, scheduled_for: Optional[datetime], db: AsyncSession, status: str = "queued",
    error: Optional[str] = None,
) -> TaskRun:
    run = TaskRun(
        task_id=task.id, user_id=task.user_id, status=status, trigger=trigger, scheduled_for=scheduled_for,
        error=error, finished_at=now_utc() if status in ("skipped", "failed") else None,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def start_manual_run(task: ScheduledTask, db: AsyncSession) -> TaskRun:
    """'지금 실행': 일정(next_run_at)은 바꾸지 않고 한 회차만 즉시 실행한다."""
    if await has_active_run(task.id, db):
        raise HTTPException(status_code=409, detail="이 작업이 이미 실행 중입니다")
    if task.conversation_id and RunRegistry.is_running(task.conversation_id):
        raise HTTPException(status_code=409, detail="결과 대화에서 에이전트가 실행 중입니다")
    run = await create_run(task, "manual", now_utc(), db)
    spawn(execute_run(run.id))
    return run


async def _get_conversation(task: ScheduledTask, now: datetime, db: AsyncSession) -> Conversation:
    if task.conversation_id and not task.new_conversation_each_run:
        conv = await db.get(Conversation, task.conversation_id)
        if conv and conv.user_id == task.user_id:
            return conv
    title = f"[예약] {task.name}"
    if task.new_conversation_each_run:
        title += f" · {_local_label(task, now, '%m/%d %H:%M')}"
    conv = await ChatService.create_conversation(
        task.user_id,
        ConversationCreate(title=title[:255], llm_provider=task.llm_provider, model_name=task.model_name),
        db,
    )
    if not task.new_conversation_each_run:
        task.conversation_id = conv.id
        await db.commit()
    return conv


async def execute_run(run_id: str) -> None:
    from app.agent.orchestrator import AgentOrchestrator
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = await db.get(TaskRun, run_id)
        if run is None:
            return
        task = await db.get(ScheduledTask, run.task_id)
        if task is None:
            run.status, run.error, run.finished_at = "failed", "작업이 삭제되었습니다", now_utc()
            await db.commit()
            return

        status, error, full_response, agent_steps = "failed", None, "", []
        rules, no_alert = "", False
        conv_id: Optional[str] = None
        try:
            started = now_utc()
            conv = await _get_conversation(task, started, db)
            conv_id = conv.id
            run.conversation_id = conv_id

            if RunRegistry.is_running(conv_id):
                run.status, run.error, run.finished_at = "skipped", "결과 대화가 사용 중이어서 이번 회차를 건너뛰었습니다", now_utc()
                task.last_run_at, task.last_status = started, "skipped"
                await db.commit()
                return

            run.status, run.started_at = "running", started
            await db.commit()

            user_input = render(
                "scheduled_run", when=_local_label(task, started, "%Y-%m-%d %H:%M"), timezone=task.timezone, prompt=task.prompt
            )
            rules = notify_rules(task) if run.trigger == "schedule" else ""  # 수동 실행은 항상 결과를 보여 준다
            if rules:
                user_input = f"{user_input}\n\n{rules}"
            await ChatService.save_message(conv_id, "user", user_input, db)

            from app.services.agent_service import AgentService

            runtime = await AgentService.runtime_for_task(task, db)  # 지정된 에이전트의 최신 발행 버전 (없으면 기본 에이전트)
            orchestrator = AgentOrchestrator(
                task.user_id,
                runtime=runtime,
                llm_provider=task.llm_provider,
                model=task.model_name,
                headless=True,
                allow_mcp=task.allow_mcp,
                allow_browser=task.allow_browser,
            )
            cancelled = False
            try:
                async with asyncio.timeout(settings.SCHEDULER_RUN_TIMEOUT_SECONDS):
                    async for event in cancellable_events(conv_id, task.user_id, orchestrator.run(user_input, conv_id, db)):
                        t = event.get("type")
                        if t == "token":
                            full_response += event.get("content", "")
                        elif t in ("thought", "tool_call", "tool_result"):
                            agent_steps.append(event)
                        elif t == "error":
                            error = event.get("message") or "에이전트 오류"
                        elif t == "cancelled":
                            cancelled = True
            except TimeoutError:
                error = f"제한 시간({settings.SCHEDULER_RUN_TIMEOUT_SECONDS}초)을 초과했습니다"
            except Exception as e:  # noqa: BLE001
                logger.exception("[scheduler] 실행 오류 task=%s", task.id)
                error = f"{type(e).__name__}: {e}"

            if cancelled:
                status = "cancelled"
            elif error:
                status = "failed"
            elif not full_response.strip():
                status, error = "failed", "에이전트가 응답을 만들지 못했습니다"
            else:
                status = "succeeded"

            if status == "succeeded":
                if rules:
                    full_response, no_alert = split_no_alert(full_response)
                content = full_response
            elif status == "cancelled":
                content = full_response + ("\n\n" if full_response else "") + CANCEL_NOTE
            else:
                content = (full_response + "\n\n" if full_response else "") + f"⚠️ 예약 실행 실패: {error}"
            saved = await ChatService.save_message(conv_id, "assistant", content, db, agent_steps=agent_steps)
            maybe_suggest_followups(task, saved.id, full_response, status, no_alert)
            run.summary = _summarize(full_response if full_response else (error or ""))
        except Exception as e:  # noqa: BLE001 — 어떤 경우에도 run 이 'running' 으로 남지 않게 한다
            logger.exception("[scheduler] run 처리 실패 run=%s", run_id)
            status, error = "failed", f"{type(e).__name__}: {e}"
            await db.rollback()
            run = await db.get(TaskRun, run_id)
            task = await db.get(ScheduledTask, run.task_id) if run else None

        if run is None:
            return
        run.status, run.error, run.finished_at = status, error, now_utc()
        run.notify = should_notify(task, status, no_alert, run.trigger) if task is not None else True
        if conv_id:
            run.conversation_id = conv_id
        if task is not None:
            task.last_run_at = run.started_at or run.finished_at
            task.last_status = status
            if status == "succeeded" and run.trigger == "schedule" and full_response.strip() and not no_alert:
                task.last_result = full_response[:PREVIOUS_RESULT_MAX]  # on_change 의 비교 기준: 알린 마지막 결과
            # 수동 실행의 실패는 자동 일시중지 판단에 쓰지 않는다 (사용자가 직접 시험하는 중일 수 있음)
            if run.trigger == "schedule":
                if status == "succeeded":
                    task.consecutive_failures = 0
                elif status == "failed":
                    task.consecutive_failures += 1
                    if task.consecutive_failures >= settings.SCHEDULER_MAX_CONSECUTIVE_FAILURES:
                        task.enabled, task.next_run_at, task.last_status = False, None, "auto_paused"
                        logger.warning("[scheduler] 연속 실패로 자동 일시중지 task=%s", task.id)
        await db.commit()
        if task is not None and run.notify and status in ("succeeded", "failed"):
            from app.channels.outbound import notify_schedule_result

            await notify_schedule_result(task.user_id, task.name, status, full_response, error)

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.schedule import (
    EnabledRequest, RunResponse, RunStarted, TaskInput, TaskResponse, TaskUpdate, UnreadCount,
)
from app.services.schedule_service import ScheduleService
from app.services.task_runner import start_manual_run

router = APIRouter()


async def _one(task, db) -> TaskResponse:
    return (await ScheduleService.to_responses([task], db))[0]


@router.get("", response_model=List[TaskResponse])
async def list_tasks(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await ScheduleService.to_responses(await ScheduleService.list_tasks(current_user.id, db), db)


@router.post("", response_model=TaskResponse)
async def create_task(data: TaskInput, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await _one(await ScheduleService.create_task(current_user.id, data, db), db)


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """아이콘 바의 읽지 않음 표시용: 아직 확인하지 않은 실행 결과 수."""
    return UnreadCount(count=await ScheduleService.unread_count(current_user.id, db))


@router.post("/runs/{run_id}/read")
async def mark_run_read(run_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ScheduleService.mark_run_read(run_id, current_user.id, db)
    return {"status": "ok"}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    return await _one(await ScheduleService.get_task(task_id, current_user.id, db), db)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str, data: TaskUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)
):
    task = await ScheduleService.get_task(task_id, current_user.id, db)
    return await _one(await ScheduleService.update_task(task, data, db), db)


@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ScheduleService.delete_task(await ScheduleService.get_task(task_id, current_user.id, db), db)
    return {"status": "deleted"}


@router.post("/{task_id}/enabled", response_model=TaskResponse)
async def set_enabled(
    task_id: str, data: EnabledRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)
):
    """일시중지(false) / 재개(true). 재개하면 다음 실행 시각을 다시 계산하고 연속 실패 수를 초기화한다."""
    task = await ScheduleService.get_task(task_id, current_user.id, db)
    return await _one(await ScheduleService.set_enabled(task, data.enabled, db), db)


@router.post("/{task_id}/run", response_model=RunStarted, status_code=202)
async def run_now(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """'지금 실행': 예약 일정은 그대로 두고 한 회차를 바로 실행한다."""
    task = await ScheduleService.get_task(task_id, current_user.id, db)
    run = await start_manual_run(task, db)
    return RunStarted(run_id=run.id, status=run.status)


@router.get("/{task_id}/runs", response_model=List[RunResponse])
async def list_runs(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ScheduleService.get_task(task_id, current_user.id, db)
    return [ScheduleService.run_response(r) for r in await ScheduleService.list_runs(task_id, current_user.id, db)]


@router.post("/{task_id}/read")
async def mark_task_read(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    await ScheduleService.get_task(task_id, current_user.id, db)
    await ScheduleService.mark_task_read(task_id, current_user.id, db)
    return {"status": "ok"}

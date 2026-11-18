"""Functions API: 함수·버전·별칭·시크릿·실행·이력·취소, 그리고 관리자 중지 스위치.

모든 경로는 로그인한 본인의 함수에만 동작하고(남의 것은 404), 기능이 꺼져 있거나 허용되지 않은 사용자는 막는다.
패키지(zip)는 Drive 에 올려 둔 파일을 골라 등록한다. 등록 시 내용을 Functions 저장소로 복사해 고정하므로
이후 Drive 파일을 바꾸거나 지워도 이미 만든 버전은 변하지 않는다.
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services import drive_service, drive_storage
from app.services import function_service as fsvc
from app.services import function_trigger_service as tsvc
from app.services.app_policy import RateLimiter, is_admin_email
from app.services.function_dispatcher import get_dispatcher
from app.services.function_service import FunctionError, run_dict

router = APIRouter()  # /api/functions
runs_router = APIRouter()  # /api/runs
admin_router = APIRouter()  # /api/admin/functions
triggers_router = APIRouter()  # /api/fn-triggers
hooks_router = APIRouter()  # /api/fn-hooks (로그인 없음: 토큰으로만 호출)
_hook_limiter = RateLimiter(settings.FUNCTION_WEBHOOK_RATE_PER_MIN)
_hook_ip_limiter = RateLimiter(settings.FUNCTION_WEBHOOK_RATE_PER_MIN * 3)


def allowed_user(user: User = Depends(get_current_user)) -> User:
    fsvc.require_allowed(user)
    return user


def admin_user(user: User = Depends(get_current_user)) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다")
    return user


class FunctionCreate(BaseModel):
    name: str
    description: str = ""
    drive_node_id: str = Field(description="Drive 에 올려 둔 zip 파일의 노드 id")


class VersionCreate(BaseModel):
    drive_node_id: str


class DescriptionUpdate(BaseModel):
    description: str = Field(default="", max_length=500)


class AliasSet(BaseModel):
    version: int


class SecretSet(BaseModel):
    value: str


class InvokeRequest(BaseModel):
    event: Any = Field(default_factory=dict)
    ref: Optional[str] = Field(default=None, description="버전 번호 또는 별칭. 없으면 latest")
    wait: bool = Field(default=False, description="true 면 FUNCTION_SYNC_WAIT_SECONDS 까지 결과를 기다린다")
    idempotency_key: Optional[str] = Field(default=None, max_length=80)


class DisableRequest(BaseModel):
    reason: str = Field(default="", max_length=255)


async def _read_drive_zip(db: AsyncSession, user_id: str, node_id: str) -> tuple:
    """Drive 의 내 파일을 읽는다. 반환: (zip 바이트, source_ref)"""
    if not drive_storage.enabled():
        raise FunctionError(503, "Drive 를 사용할 수 없어 패키지를 읽지 못합니다")
    try:
        node = await drive_service.get_owned(db, user_id, node_id)
    except drive_service.DriveError as e:
        raise FunctionError(e.status, e.message)
    if node.type != "file" or not node.storage_key:
        raise FunctionError(400, "zip 파일을 선택하세요")
    if int(node.size_bytes or 0) > settings.FUNCTION_PACKAGE_MAX_MB * 1024 * 1024:
        raise FunctionError(413, f"패키지는 {settings.FUNCTION_PACKAGE_MAX_MB}MB 까지 올릴 수 있습니다")
    data = bytearray()
    async for chunk in drive_storage.storage.stream(node.storage_key):
        data.extend(chunk)
    return bytes(data), {"drive_node_id": node.id, "drive_path": await drive_service.node_path(db, node)}


def _fn_dict(fn, last: Optional[dict] = None) -> dict:
    d = {
        "id": fn.id, "name": fn.name, "description": fn.description, "runtime": fn.runtime, "latest_version": fn.latest_version,
        "disabled": bool(fn.disabled), "disabled_reason": fn.disabled_reason,
        "created_at": fn.created_at.isoformat() if fn.created_at else None, "updated_at": fn.updated_at.isoformat() if fn.updated_at else None,
    }
    if last is not None:
        d["last_run"] = {"status": last["status"], "queued_at": last["queued_at"].isoformat() if last["queued_at"] else None}
    return d


def _ver_dict(v) -> dict:
    return {"version": v.version, "sha256": v.sha256, "size_bytes": int(v.size_bytes), "unpacked_bytes": int(v.unpacked_bytes), "file_count": v.file_count,
            "config": v.config, "source": v.source, "source_ref": v.source_ref, "created_at": v.created_at.isoformat() if v.created_at else None}


@router.get("/info")
async def info(user: User = Depends(get_current_user)):
    """화면이 메뉴·안내를 정하는 데 쓴다: 기능 켜짐 여부, 이 사용자의 허용 여부, 한도."""
    return {
        "enabled": settings.FUNCTION_ENABLED, "allowed": fsvc.is_allowed(user), "is_admin": is_admin_email(user.email),
        "runtimes": ["python3.12", "bun"], "allow_network": False,  # 첫 버전은 네트워크 차단만 지원한다
        "limits": {
            "package_mb": settings.FUNCTION_PACKAGE_MAX_MB, "timeout_default": settings.FUNCTION_TIMEOUT_DEFAULT, "timeout_max": settings.FUNCTION_TIMEOUT_MAX,
            "memory_default_mb": settings.FUNCTION_MEMORY_DEFAULT_MB, "memory_max_mb": settings.FUNCTION_MEMORY_MAX_MB, "event_kb": settings.FUNCTION_EVENT_MAX_KB,
            "result_kb": settings.FUNCTION_RESULT_MAX_KB, "log_kb": settings.FUNCTION_LOG_MAX_KB, "sync_wait_seconds": settings.FUNCTION_SYNC_WAIT_SECONDS,
            "retention_days": settings.FUNCTION_RUN_RETENTION_DAYS, "runs_per_day": settings.FUNCTION_RUNS_PER_DAY_PER_USER,
        },
    }


@router.get("")
async def list_functions(user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    fns = await fsvc.list_functions(db, user.id)
    last = await fsvc.last_runs(db, [f.id for f in fns])
    return {"functions": [_fn_dict(f, last.get(f.id) or {"status": None, "queued_at": None}) for f in fns]}


@router.post("")
async def create_function(data: FunctionCreate, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    zip_bytes, ref = await _read_drive_zip(db, user.id, data.drive_node_id)
    fn, ver = await fsvc.create_function(db, user, data.name, data.description, zip_bytes, source="drive", source_ref=ref)
    return {**_fn_dict(fn), "version": _ver_dict(ver)}


@router.get("/{function_id}")
async def get_function(function_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    fn = await fsvc.get_function(db, user.id, function_id)
    return {**_fn_dict(fn), "versions": [_ver_dict(v) for v in await fsvc.list_versions(db, fn)], "aliases": await fsvc.get_aliases(db, fn),
            "secrets": await fsvc.list_secret_keys(db, user.id, fn.id)}


@router.put("/{function_id}")
async def update_function(function_id: str, data: DescriptionUpdate, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    return _fn_dict(await fsvc.update_description(db, user.id, function_id, data.description))


@router.delete("/{function_id}")
async def delete_function(function_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.delete_function(db, user.id, function_id)
    return {"deleted": True}


@router.post("/{function_id}/versions")
async def add_version(function_id: str, data: VersionCreate, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    zip_bytes, ref = await _read_drive_zip(db, user.id, data.drive_node_id)
    _, ver, created = await fsvc.add_version(db, user, function_id, zip_bytes, source="drive", source_ref=ref)
    return {"version": _ver_dict(ver), "created": created}


@router.put("/{function_id}/aliases/{alias}")
async def put_alias(function_id: str, alias: str, data: AliasSet, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.set_alias(db, user.id, function_id, alias, data.version)
    return {"alias": alias, "version": data.version}


@router.delete("/{function_id}/aliases/{alias}")
async def remove_alias(function_id: str, alias: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.delete_alias(db, user.id, function_id, alias)
    return {"deleted": True}


@router.put("/{function_id}/secrets/{key}")
async def put_secret(function_id: str, key: str, data: SecretSet, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.put_secret(db, user.id, function_id, key, data.value)
    return {"key": key}  # 값은 돌려주지 않는다


@router.delete("/{function_id}/secrets/{key}")
async def remove_secret(function_id: str, key: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.delete_secret(db, user.id, function_id, key)
    return {"deleted": True}


@router.post("/{function_id}/invoke")
async def invoke(function_id: str, data: InvokeRequest, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    """실행을 큐에 넣는다. wait=true 면 최대 FUNCTION_SYNC_WAIT_SECONDS 기다려 결과까지 돌려주고, 넘으면 202 로 run_id 만 준다."""
    run = await fsvc.invoke(db, user, function_id, data.event, ref=data.ref, trigger="api" if data.wait else "manual", idempotency_key=data.idempotency_key)
    disp = get_dispatcher()
    disp.kick()
    done = False
    if data.wait:
        done = await disp.wait_for(run.id, settings.FUNCTION_SYNC_WAIT_SECONDS)
        run = await fsvc.get_run(db, user.id, run.id)
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=200 if (done or not data.wait) else 202, content={"run": run_dict(run, detail=done), "done": done})


# ── 실행 이력 ─────────────────────────────────────────────────
@runs_router.get("")
async def list_runs(function_id: Optional[str] = None, status: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    runs = await fsvc.list_runs(db, user.id, function_id, status, limit, offset)
    return {"runs": [run_dict(r) for r in runs]}


@runs_router.get("/{run_id}")
async def get_run(run_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    return run_dict(await fsvc.get_run(db, user.id, run_id), detail=True)


@runs_router.get("/{run_id}/logs")
async def get_logs(run_id: str, after: int = Query(0, ge=0), user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    """로그를 바이트 오프셋(after)부터 돌려준다. 로그는 실행이 끝나면 기록된다(실행 중에는 비어 있다)."""
    run = await fsvc.get_run(db, user.id, run_id)
    raw = (run.log or "").encode()
    chunk = raw[after:]
    return {"log": chunk.decode("utf-8", errors="replace"), "next": len(raw), "done": run.status in fsvc.TERMINAL, "truncated": bool(run.log_truncated)}


@runs_router.post("/{run_id}/cancel")
async def cancel_run(run_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    run = await fsvc.request_cancel(db, user.id, run_id)
    get_dispatcher().cancel_local(run_id)  # 이 프로세스에서 실행 중이면 곧바로 중단한다 (다른 프로세스는 폴링으로 반영)
    return run_dict(run)


# ── 관리자 ────────────────────────────────────────────────────
@admin_router.get("")
async def admin_list(_: User = Depends(admin_user), db: AsyncSession = Depends(get_session)):
    return {"functions": [{**_fn_dict(f), "user_id": f.user_id} for f in await fsvc.list_all_functions(db)]}


@admin_router.post("/{function_id}/disable")
async def admin_disable(function_id: str, data: DisableRequest, _: User = Depends(admin_user), db: AsyncSession = Depends(get_session)):
    fn = await fsvc.set_disabled(db, function_id, True, data.reason)
    disp = get_dispatcher()
    from sqlalchemy import select

    from app.models.function import FunctionRun

    for rid in (await db.execute(select(FunctionRun.id).where(FunctionRun.function_id == fn.id, FunctionRun.status.in_(("starting", "running"))))).scalars().all():
        disp.cancel_local(rid)
    return _fn_dict(fn)


@admin_router.post("/{function_id}/enable")
async def admin_enable(function_id: str, _: User = Depends(admin_user), db: AsyncSession = Depends(get_session)):
    return _fn_dict(await fsvc.set_disabled(db, function_id, False))


# ── 트리거 (예약·웹훅) ────────────────────────────────────────
class TriggerCreate(BaseModel):
    kind: str = Field(pattern="^(schedule|webhook)$")
    name: str = Field(default="", max_length=100)
    ref: Optional[str] = Field(default=None, description="버전 번호 또는 별칭. 없으면 latest (별칭을 권장: 새 버전이 나와도 바뀌지 않는다)")
    schedule_type: Optional[str] = None
    schedule_time: Optional[str] = None
    weekdays: Optional[List[int]] = None
    day_of_month: Optional[int] = None
    interval_hours: Optional[int] = None
    run_at: Optional[datetime] = None
    timezone: Optional[str] = None


class TriggerPatch(BaseModel):
    enabled: bool


@router.get("/{function_id}/triggers")
async def list_function_triggers(function_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await fsvc.get_function(db, user.id, function_id)
    ts = await tsvc.list_triggers(db, user.id, function_id)
    st = await tsvc.run_statuses(db, ts)
    return {"triggers": [tsvc.trigger_dict(t, run_status=st.get(t.last_run_id)) for t in ts]}


@router.post("/{function_id}/triggers")
async def create_trigger(function_id: str, data: TriggerCreate, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    """예약 또는 웹훅 트리거를 만든다. 웹훅의 토큰(주소)은 이 응답에서만 볼 수 있다."""
    if data.kind == "webhook":
        t, token = await tsvc.create_webhook(db, user, function_id, data.name, data.ref)
        return {**tsvc.trigger_dict(t, token), "token": token}
    if not data.schedule_type:
        raise FunctionError(400, "schedule_type 이 필요합니다")
    run_at = data.run_at.astimezone(__import__("datetime").timezone.utc).replace(tzinfo=None) if data.run_at and data.run_at.tzinfo else data.run_at
    t = await tsvc.create_schedule(db, user, function_id, data.name, data.ref, data.schedule_type, schedule_time=data.schedule_time, weekdays=data.weekdays,
                                   day_of_month=data.day_of_month, interval_hours=data.interval_hours, run_at=run_at, timezone_name=data.timezone)
    return tsvc.trigger_dict(t)


@triggers_router.get("")
async def list_all_triggers(user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    ts = await tsvc.list_triggers(db, user.id)
    st = await tsvc.run_statuses(db, ts)
    return {"triggers": [tsvc.trigger_dict(t, run_status=st.get(t.last_run_id)) for t in ts]}


@triggers_router.patch("/{trigger_id}")
async def patch_trigger(trigger_id: str, data: TriggerPatch, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    return tsvc.trigger_dict(await tsvc.set_enabled(db, user.id, trigger_id, data.enabled))


@triggers_router.delete("/{trigger_id}")
async def remove_trigger(trigger_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    await tsvc.delete_trigger(db, user.id, trigger_id)
    return {"deleted": True}


@triggers_router.post("/{trigger_id}/regenerate")
async def regenerate_hook(trigger_id: str, user: User = Depends(allowed_user), db: AsyncSession = Depends(get_session)):
    """웹훅 토큰을 새로 만든다. 이전 주소는 즉시 쓸 수 없게 된다."""
    t, token = await tsvc.regenerate_webhook(db, user.id, trigger_id)
    return {**tsvc.trigger_dict(t, token), "token": token}


@hooks_router.post("/{token}")
async def call_webhook(token: str, request: Request, wait: bool = Query(False), db: AsyncSession = Depends(get_session)):
    """웹훅 수신: 본문(JSON)을 이벤트로 함수를 실행한다. 로그인 없이 토큰만으로 호출한다.
    알 수 없거나 꺼진 토큰은 모두 같은 404 이고, 토큰·IP 별로 호출 횟수를 제한한다. wait=true 면 결과까지 기다린다."""
    from fastapi.responses import JSONResponse

    ip = request.client.host if request.client else ""
    if not _hook_ip_limiter.allow(ip) or not _hook_limiter.allow(token[:16]):
        return JSONResponse({"detail": "요청이 너무 많습니다. 잠시 후 다시 시도하세요"}, status_code=429, headers={"Retry-After": "30"})
    raw = await request.body()
    if len(raw) > settings.FUNCTION_EVENT_MAX_KB * 1024:
        raise FunctionError(413, f"본문은 {settings.FUNCTION_EVENT_MAX_KB}KB 까지 가능합니다")
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        event = {"body": raw.decode("utf-8", errors="replace")}  # JSON 이 아니면 문자열로 감싸 전달한다
    run = await tsvc.fire_webhook(db, token, event)
    disp = get_dispatcher()
    disp.kick()
    if not wait:
        return JSONResponse({"run_id": run.id, "status": run.status}, status_code=202)
    done = await disp.wait_for(run.id, settings.FUNCTION_SYNC_WAIT_SECONDS)
    run = await fsvc.get_run(db, run.user_id, run.id)
    return JSONResponse({"run_id": run.id, "status": run.status, "result": json.loads(run.result) if (done and run.result) else None, "error": run.error if done else None}, status_code=200 if done else 202)

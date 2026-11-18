"""Functions 서비스: 등록·버전·별칭·시크릿·호출(큐 적재)·취소·이력·정리.

실행 자체는 function_dispatcher 가 맡는다. 여기서는 DB 상태와 한도(쿼터)를 다룬다.
모든 접근은 소유자 확인을 거치며 남의 항목은 '없음'(404)으로 응답한다.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.config import settings
from app.core import crypto
from app.models.function import Function, FunctionAlias, FunctionRun, FunctionSecret, FunctionVersion
from app.services import drive_storage
from app.services.app_policy import is_admin_email
from app.services.function_package import ENV_NAME_RE, NAME_RE, RESERVED_ENV, PackageError, inspect_zip

ACTIVE = ("queued", "starting", "running")
TERMINAL = ("succeeded", "failed", "timeout", "cancelled", "rejected")
ALIAS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
BIG_RUN_COLUMNS = (FunctionRun.input, FunctionRun.result, FunctionRun.log)


class FunctionError(Exception):
    """사용자에게 그대로 보여 줄 수 있는 오류. status 는 HTTP 상태."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def storage_ready() -> bool:
    return bool(settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY)


def is_allowed(user) -> bool:
    """기능이 켜져 있고, 관리자이거나 허용 목록(FUNCTION_ALLOWED_EMAILS, '*' 는 모두)에 있는 사용자만 쓸 수 있다."""
    if not settings.FUNCTION_ENABLED:
        return False
    if is_admin_email(getattr(user, "email", None)):
        return True
    allowed = {e.strip().lower() for e in settings.FUNCTION_ALLOWED_EMAILS.split(",") if e.strip()}
    return "*" in allowed or (getattr(user, "email", "") or "").lower() in allowed


def require_allowed(user) -> None:
    if not settings.FUNCTION_ENABLED:
        raise FunctionError(503, "Functions 기능이 꺼져 있습니다 (FUNCTION_ENABLED)")
    if not is_allowed(user):
        raise FunctionError(403, "Functions 를 사용할 권한이 없습니다. 관리자에게 문의하세요")
    if not storage_ready():
        raise FunctionError(503, "패키지 저장소(MinIO)가 설정되지 않았습니다")


def package_key(user_id: str, function_id: str, version: int) -> str:
    return f"functions/{user_id}/{function_id}/{version}.tar.gz"


# ── 조회 ──────────────────────────────────────────────────────
async def get_function(db: AsyncSession, user_id: str, function_id: str, *, admin: bool = False) -> Function:
    fn = await db.get(Function, function_id, populate_existing=True)
    if fn is None or fn.deleted_at is not None or (not admin and fn.user_id != user_id):
        raise FunctionError(404, "함수를 찾을 수 없습니다")
    return fn


async def list_functions(db: AsyncSession, user_id: str) -> list:
    return list((await db.execute(select(Function).where(Function.user_id == user_id, Function.deleted_at.is_(None)).order_by(Function.updated_at.desc()))).scalars().all())


async def last_runs(db: AsyncSession, function_ids: list) -> dict:
    """함수별 가장 최근 실행의 (status, queued_at). 큰 열은 읽지 않는다."""
    out = {}
    for fid in function_ids:
        r = (await db.execute(select(FunctionRun.status, FunctionRun.queued_at).where(FunctionRun.function_id == fid).order_by(FunctionRun.queued_at.desc()).limit(1))).first()
        if r:
            out[fid] = {"status": r[0], "queued_at": r[1]}
    return out


async def list_versions(db: AsyncSession, fn: Function) -> list:
    return list((await db.execute(select(FunctionVersion).where(FunctionVersion.function_id == fn.id).order_by(FunctionVersion.version.desc()))).scalars().all())


async def get_aliases(db: AsyncSession, fn: Function) -> dict:
    rows = (await db.execute(select(FunctionAlias).where(FunctionAlias.function_id == fn.id))).scalars().all()
    out = {a.alias: a.version for a in rows}
    out["latest"] = fn.latest_version
    return out


async def resolve_version(db: AsyncSession, fn: Function, ref: Optional[str]) -> FunctionVersion:
    """ref: None/'latest' → 최신, 숫자 → 그 버전, 그 밖 → 별칭."""
    ref = (str(ref).strip() if ref is not None else "") or "latest"
    if ref == "latest":
        number = fn.latest_version
    elif ref.isdigit():
        number = int(ref)
    else:
        a = await db.get(FunctionAlias, (fn.id, ref))
        if a is None:
            raise FunctionError(404, f"별칭을 찾을 수 없습니다: {ref}")
        number = a.version
    v = (await db.execute(select(FunctionVersion).where(FunctionVersion.function_id == fn.id, FunctionVersion.version == number))).scalar_one_or_none()
    if v is None:
        raise FunctionError(404, f"버전을 찾을 수 없습니다: {ref}")
    return v


# ── 등록·버전 ─────────────────────────────────────────────────
async def _store_version(db: AsyncSession, fn: Function, zip_bytes: bytes, source: str, source_ref: Optional[dict], store) -> tuple:
    try:
        info = inspect_zip(zip_bytes)
    except PackageError as e:
        raise FunctionError(400, str(e))
    if fn.latest_version and info.config["runtime"] != fn.runtime:
        raise FunctionError(400, f"런타임을 바꿀 수 없습니다 (함수: {fn.runtime}, 패키지: {info.config['runtime']})")
    versions = list((await db.execute(select(FunctionVersion).where(FunctionVersion.function_id == fn.id))).scalars().all())
    same = next((v for v in versions if v.sha256 == info.sha256), None)
    if same is not None:
        return same, False  # 같은 내용은 새 버전을 만들지 않는다
    if len(versions) >= settings.FUNCTION_VERSIONS_MAX:
        raise FunctionError(400, f"버전은 {settings.FUNCTION_VERSIONS_MAX}개까지 둘 수 있습니다. 안 쓰는 함수를 정리하세요")
    number = fn.latest_version + 1
    key = package_key(fn.user_id, fn.id, number)
    import io

    try:
        await store.put(key, io.BytesIO(info.tar_gz), len(info.tar_gz), "application/gzip")
    except Exception as e:  # noqa: BLE001
        raise FunctionError(502, f"패키지를 저장하지 못했습니다: {type(e).__name__}")
    ver = FunctionVersion(function_id=fn.id, version=number, sha256=info.sha256, storage_key=key, size_bytes=len(info.tar_gz), tar_bytes=info.tar_bytes,
                          unpacked_bytes=info.unpacked_bytes, file_count=info.file_count, config=info.config, source=source, source_ref=source_ref)
    db.add(ver)
    fn.latest_version = number
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        try:
            await store.remove(key)
        except Exception:  # noqa: BLE001
            pass
        raise
    return ver, True


async def create_function(db: AsyncSession, user, name: str, description: str, zip_bytes: bytes, source: str = "drive", source_ref: Optional[dict] = None, store=None) -> tuple:
    require_allowed(user)
    store = store or drive_storage.storage
    name = (name or "").strip()
    if not NAME_RE.match(name):
        raise FunctionError(400, "이름은 영문·숫자·_·- 로 시작과 끝을 이루는 64자 이하여야 합니다")
    existing = (await db.execute(select(Function.id).where(Function.user_id == user.id, Function.name == name, Function.deleted_key == ""))).first()
    if existing:
        raise FunctionError(409, f"같은 이름의 함수가 이미 있습니다: {name}")
    try:
        runtime = inspect_zip(zip_bytes).config["runtime"]
    except PackageError as e:
        raise FunctionError(400, str(e))
    fn = Function(user_id=user.id, name=name, description=(description or "")[:500], runtime=runtime)
    db.add(fn)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise FunctionError(409, f"같은 이름의 함수가 이미 있습니다: {name}")
    try:
        ver, _ = await _store_version(db, fn, zip_bytes, source, source_ref, store)
    except Exception:
        await db.delete(fn)  # 첫 버전을 못 만들면 빈 함수를 남기지 않는다
        await db.commit()
        raise
    return fn, ver


async def add_version(db: AsyncSession, user, function_id: str, zip_bytes: bytes, source: str = "drive", source_ref: Optional[dict] = None, store=None) -> tuple:
    require_allowed(user)
    fn = await get_function(db, user.id, function_id)
    return (fn, *(await _store_version(db, fn, zip_bytes, source, source_ref, store or drive_storage.storage)))


async def update_description(db: AsyncSession, user_id: str, function_id: str, description: str) -> Function:
    fn = await get_function(db, user_id, function_id)
    fn.description = (description or "")[:500]
    await db.commit()
    return fn


async def set_alias(db: AsyncSession, user_id: str, function_id: str, alias: str, version: int) -> None:
    fn = await get_function(db, user_id, function_id)
    if alias == "latest" or not ALIAS_RE.match(alias):
        raise FunctionError(400, "별칭은 영문으로 시작하는 40자 이하의 영문·숫자·_·- 이어야 하고 'latest' 는 쓸 수 없습니다")
    v = (await db.execute(select(FunctionVersion.id).where(FunctionVersion.function_id == fn.id, FunctionVersion.version == version))).first()
    if v is None:
        raise FunctionError(404, f"버전을 찾을 수 없습니다: {version}")
    a = await db.get(FunctionAlias, (fn.id, alias))
    if a is None:
        db.add(FunctionAlias(function_id=fn.id, alias=alias, version=version))
    else:
        a.version = version
    await db.commit()


async def delete_alias(db: AsyncSession, user_id: str, function_id: str, alias: str) -> None:
    fn = await get_function(db, user_id, function_id)
    await db.execute(delete(FunctionAlias).where(FunctionAlias.function_id == fn.id, FunctionAlias.alias == alias))
    await db.commit()


async def delete_function(db: AsyncSession, user_id: str, function_id: str) -> None:
    """소프트 삭제: 실행 중인 것이 있으면 거부, 시크릿은 즉시 지우고 패키지·이력은 보관 기간 뒤 정리한다."""
    fn = await get_function(db, user_id, function_id)
    active = (await db.execute(select(func.count()).select_from(FunctionRun).where(FunctionRun.function_id == fn.id, FunctionRun.status.in_(ACTIVE)))).scalar() or 0
    if active:
        raise FunctionError(409, f"실행 중이거나 대기 중인 작업이 {active}개 있습니다. 끝난 뒤 삭제하세요")
    await db.execute(delete(FunctionSecret).where(FunctionSecret.function_id == fn.id))
    fn.deleted_at, fn.deleted_key = _now(), fn.id
    await db.commit()


# ── 시크릿 ────────────────────────────────────────────────────
async def put_secret(db: AsyncSession, user_id: str, function_id: str, key: str, value: str) -> None:
    fn = await get_function(db, user_id, function_id)
    if not ENV_NAME_RE.match(key) or key.startswith("FN_") or key in RESERVED_ENV:
        raise FunctionError(400, f"사용할 수 없는 이름입니다: {key}")
    if not value or len(value) > 4096:
        raise FunctionError(400, "값은 1~4096자여야 합니다")
    row = await db.get(FunctionSecret, (fn.id, key))
    if row is None:
        count = (await db.execute(select(func.count()).select_from(FunctionSecret).where(FunctionSecret.function_id == fn.id))).scalar() or 0
        if count >= 50:
            raise FunctionError(400, "시크릿은 50개까지 등록할 수 있습니다")
        db.add(FunctionSecret(function_id=fn.id, key=key, value_enc=crypto.encrypt(value)))
    else:
        row.value_enc = crypto.encrypt(value)
    await db.commit()


async def list_secret_keys(db: AsyncSession, user_id: str, function_id: str) -> list:
    fn = await get_function(db, user_id, function_id)
    return list((await db.execute(select(FunctionSecret.key).where(FunctionSecret.function_id == fn.id).order_by(FunctionSecret.key))).scalars().all())


async def delete_secret(db: AsyncSession, user_id: str, function_id: str, key: str) -> None:
    fn = await get_function(db, user_id, function_id)
    await db.execute(delete(FunctionSecret).where(FunctionSecret.function_id == fn.id, FunctionSecret.key == key))
    await db.commit()


async def load_secrets(db: AsyncSession, function_id: str) -> dict:
    rows = (await db.execute(select(FunctionSecret).where(FunctionSecret.function_id == function_id))).scalars().all()
    out = {}
    for r in rows:
        try:
            out[r.key] = crypto.decrypt(r.value_enc)
        except ValueError:
            continue  # 복호화할 수 없는 값은 주입하지 않는다
    return out


# ── 호출·취소·이력 ────────────────────────────────────────────
async def invoke(db: AsyncSession, user, function_id: str, event, ref: Optional[str] = None, trigger: str = "manual",
                 idempotency_key: Optional[str] = None, parent_run_id: Optional[str] = None) -> FunctionRun:
    """실행을 큐에 넣는다(실제 실행은 디스패처). 한도·정지 상태·크기를 먼저 검사한다."""
    require_allowed(user)
    fn = await get_function(db, user.id, function_id)
    if fn.disabled:
        raise FunctionError(403, f"관리자가 이 함수의 실행을 중지했습니다{': ' + fn.disabled_reason if fn.disabled_reason else ''}")
    ver = await resolve_version(db, fn, ref)
    payload = json.dumps(event if event is not None else {}, ensure_ascii=False)
    if len(payload.encode()) > settings.FUNCTION_EVENT_MAX_KB * 1024:
        raise FunctionError(413, f"입력은 {settings.FUNCTION_EVENT_MAX_KB}KB 까지 가능합니다")
    if idempotency_key:
        dup = (await db.execute(select(FunctionRun).options(*[defer(c) for c in BIG_RUN_COLUMNS]).where(
            FunctionRun.user_id == user.id, FunctionRun.function_id == fn.id, FunctionRun.idempotency_key == idempotency_key,
            FunctionRun.queued_at > _now() - timedelta(hours=24)))).scalars().first()
        if dup is not None:
            return dup  # 같은 키의 요청은 새로 실행하지 않고 기존 실행을 돌려준다
    queued = (await db.execute(select(func.count()).select_from(FunctionRun).where(FunctionRun.user_id == user.id, FunctionRun.status == "queued"))).scalar() or 0
    if queued >= settings.FUNCTION_QUEUE_MAX_PER_USER:
        raise FunctionError(429, f"대기 중인 실행이 너무 많습니다 (최대 {settings.FUNCTION_QUEUE_MAX_PER_USER}개). 잠시 후 다시 시도하세요")
    today = (await db.execute(select(func.count()).select_from(FunctionRun).where(FunctionRun.user_id == user.id, FunctionRun.queued_at > _now() - timedelta(hours=24)))).scalar() or 0
    if today >= settings.FUNCTION_RUNS_PER_DAY_PER_USER:
        raise FunctionError(429, f"하루 실행 한도({settings.FUNCTION_RUNS_PER_DAY_PER_USER}회)를 넘었습니다")
    run = FunctionRun(function_id=fn.id, version=ver.version, user_id=user.id, trigger=trigger, status="queued", input=payload,
                      idempotency_key=idempotency_key, parent_run_id=parent_run_id)
    db.add(run)
    await db.commit()
    return run


async def get_run(db: AsyncSession, user_id: str, run_id: str, *, admin: bool = False) -> FunctionRun:
    run = await db.get(FunctionRun, run_id, populate_existing=True)
    if run is None or (not admin and run.user_id != user_id):
        raise FunctionError(404, "실행 기록을 찾을 수 없습니다")
    return run


async def list_runs(db: AsyncSession, user_id: str, function_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> list:
    """목록용: input/result/log 같은 큰 열은 읽지 않는다 (MySQL sort memory 오류 방지)."""
    q = select(FunctionRun).options(*[defer(c) for c in BIG_RUN_COLUMNS]).where(FunctionRun.user_id == user_id)
    if function_id:
        q = q.where(FunctionRun.function_id == function_id)
    if status:
        q = q.where(FunctionRun.status == status)
    return list((await db.execute(q.order_by(FunctionRun.queued_at.desc(), FunctionRun.id).offset(max(0, offset)).limit(max(1, min(limit, 200))))).scalars().all())


async def request_cancel(db: AsyncSession, user_id: str, run_id: str) -> FunctionRun:
    """대기 중이면 바로 취소하고, 실행 중이면 취소를 요청한다(디스패처가 컨테이너를 중단한다)."""
    run = await get_run(db, user_id, run_id)
    if run.status in TERMINAL:
        raise FunctionError(409, "이미 끝난 실행입니다")
    r = await db.execute(update(FunctionRun).where(FunctionRun.id == run.id, FunctionRun.status == "queued").values(
        status="cancelled", finished_at=_now(), error={"type": "Cancelled", "message": "시작하기 전에 취소되었습니다"}, cancel_requested=True))
    if (r.rowcount or 0) == 0:
        await db.execute(update(FunctionRun).where(FunctionRun.id == run.id).values(cancel_requested=True))
    await db.commit()
    return await get_run(db, user_id, run_id)


# ── 관리자 ────────────────────────────────────────────────────
async def set_disabled(db: AsyncSession, function_id: str, disabled: bool, reason: str = "") -> Function:
    """관리자 즉시 중지/해제. 중지하면 대기 중인 실행은 취소하고 실행 중인 것은 중단을 요청한다."""
    fn = await get_function(db, "", function_id, admin=True)
    fn.disabled, fn.disabled_reason = disabled, (reason or None) if disabled else None
    if disabled:
        await db.execute(update(FunctionRun).where(FunctionRun.function_id == fn.id, FunctionRun.status == "queued").values(
            status="cancelled", finished_at=_now(), cancel_requested=True, error={"type": "Cancelled", "message": "관리자가 함수를 중지했습니다"}))
        await db.execute(update(FunctionRun).where(FunctionRun.function_id == fn.id, FunctionRun.status.in_(("starting", "running"))).values(cancel_requested=True))
    await db.commit()
    return fn


async def list_all_functions(db: AsyncSession, limit: int = 200) -> list:
    return list((await db.execute(select(Function).where(Function.deleted_at.is_(None)).order_by(Function.updated_at.desc()).limit(limit))).scalars().all())


# ── 정리 ──────────────────────────────────────────────────────
async def purge_expired(db: AsyncSession, store=None, days: Optional[int] = None, batch: int = 500) -> dict:
    """보관 기간이 지난 실행 이력과, 삭제 후 보관 기간이 지난 함수(패키지 포함)를 영구 삭제한다."""
    days = settings.FUNCTION_RUN_RETENTION_DAYS if days is None else days
    if days <= 0:
        return {"runs": 0, "functions": 0}
    store = store or drive_storage.storage
    cutoff = _now() - timedelta(days=days)
    ids = (await db.execute(select(FunctionRun.id).where(FunctionRun.status.in_(TERMINAL), FunctionRun.finished_at < cutoff).limit(batch))).scalars().all()
    if ids:
        await db.execute(delete(FunctionRun).where(FunctionRun.id.in_(ids)))
        await db.commit()
    n_fn = 0
    for fn in (await db.execute(select(Function).where(Function.deleted_at.is_not(None), Function.deleted_at < cutoff).limit(50))).scalars().all():
        for v in (await db.execute(select(FunctionVersion).where(FunctionVersion.function_id == fn.id))).scalars().all():
            try:
                await store.remove(v.storage_key)
            except Exception:  # noqa: BLE001  이미 없거나 일시 오류
                pass
        await db.execute(delete(FunctionRun).where(FunctionRun.function_id == fn.id))
        await db.execute(delete(FunctionAlias).where(FunctionAlias.function_id == fn.id))
        await db.execute(delete(FunctionSecret).where(FunctionSecret.function_id == fn.id))
        await db.execute(delete(FunctionVersion).where(FunctionVersion.function_id == fn.id))
        await db.execute(delete(Function).where(Function.id == fn.id))
        await db.commit()
        n_fn += 1
    return {"runs": len(ids), "functions": n_fn}


def run_dict(r: FunctionRun, detail: bool = False) -> dict:
    d = {
        "id": r.id, "function_id": r.function_id, "version": r.version, "trigger": r.trigger, "status": r.status,
        "queued_at": r.queued_at.isoformat() if r.queued_at else None, "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None, "duration_ms": r.duration_ms, "cold_start_ms": r.cold_start_ms,
        "exit_code": r.exit_code, "error": r.error, "cancel_requested": bool(r.cancel_requested), "attempt": r.attempt,
    }
    if detail:
        d["input"] = json.loads(r.input) if r.input else None
        d["result"] = json.loads(r.result) if r.result else None
        d["log_truncated"] = bool(r.log_truncated)
        d["log_size"] = len((r.log or "").encode())
    return d

"""Function 디스패처: 큐(DB 의 queued 행)에서 실행을 선점해 새 컨테이너로 돌리고 결과를 기록한다.

- 선점은 조건부 UPDATE(status='queued' 일 때만 'starting' 으로)라서 서버 프로세스가 여럿이어도 한 실행은 한 번만 시작된다.
- 동시 실행 한도: 전체 FUNCTION_MAX_CONCURRENT_GLOBAL, 사용자당 FUNCTION_MAX_CONCURRENT_PER_USER. 한도에 걸린 것은 큐에서 기다린다.
- 실행 방식(RuntimeBackend)과 저장소는 주입할 수 있어 API 프로세스와 분리하거나 다른 러너로 바꿀 수 있다.
"""
import asyncio
import json
import logging
import os
import socket
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update

from app.config import settings
from app.models.function import Function, FunctionRun, FunctionVersion
from app.services import drive_storage
from app.services import function_service as fsvc
from app.services.function_runtime import RunOutcome, RunSpec, runtime as default_runtime

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Dispatcher:
    def __init__(self, runtime=None, store=None, session_factory=None):
        from app.db.session import AsyncSessionLocal

        self.runtime = runtime or default_runtime
        self.store = store or drive_storage.storage
        self.session_factory = session_factory or AsyncSessionLocal
        self.host = socket.gethostname()
        self.worker_id = f"{self.host}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self._wake = asyncio.Event()
        self._cancel: dict = {}  # run_id -> asyncio.Event (이 프로세스에서 실행 중인 것)
        self._tasks: set = set()

    def kick(self) -> None:
        self._wake.set()

    # ── 시작 복구 ────────────────────────────────────────────
    async def recover(self) -> int:
        """같은 호스트의 이전 프로세스가 맡았다가 끝내지 못한 실행을 실패로 정리하고 남은 컨테이너를 치운다."""
        async with self.session_factory() as db:
            r = await db.execute(update(FunctionRun).where(
                FunctionRun.status.in_(("starting", "running")), FunctionRun.worker_id.like(f"{self.host}:%"), FunctionRun.worker_id != self.worker_id,
            ).values(status="failed", finished_at=_now(), error={"type": "Infrastructure", "message": "서버가 재시작되어 실행이 중단되었습니다"}))
            await db.commit()
        n = r.rowcount or 0
        try:
            removed = await self.runtime.cleanup_orphans()
        except Exception:  # noqa: BLE001  Docker 가 없어도 서버는 떠야 한다
            logger.warning("[functions] 고아 컨테이너 정리 실패", exc_info=True)
            removed = 0
        if n or removed:
            logger.info("[functions] 시작 복구: 중단된 실행 %d건, 고아 컨테이너 %d개 정리", n, removed)
        return n

    # ── 큐 → 실행 ────────────────────────────────────────────
    async def dispatch_once(self) -> int:
        """한도 안에서 대기 중인 실행을 선점해 시작한다. 반환: 시작한 수."""
        started = 0
        async with self.session_factory() as db:
            active = (await db.execute(select(FunctionRun.user_id, func.count()).where(FunctionRun.status.in_(("starting", "running"))).group_by(FunctionRun.user_id))).all()
            per_user = {u: c for u, c in active}
            total = sum(per_user.values())
            queued = (await db.execute(select(FunctionRun.id, FunctionRun.user_id).where(FunctionRun.status == "queued").order_by(FunctionRun.queued_at, FunctionRun.id).limit(100))).all()
            for rid, uid in queued:
                if total >= settings.FUNCTION_MAX_CONCURRENT_GLOBAL:
                    break
                if per_user.get(uid, 0) >= settings.FUNCTION_MAX_CONCURRENT_PER_USER:
                    continue  # 이 사용자의 자리가 날 때까지 기다린다 (다른 사용자의 실행은 막지 않는다)
                r = await db.execute(update(FunctionRun).where(FunctionRun.id == rid, FunctionRun.status == "queued").values(status="starting", worker_id=self.worker_id, started_at=_now()))
                await db.commit()
                if (r.rowcount or 0) != 1:
                    continue  # 다른 프로세스가 먼저 가져갔거나 취소되었다
                total += 1
                per_user[uid] = per_user.get(uid, 0) + 1
                started += 1
                t = asyncio.create_task(self.execute(rid))
                self._tasks.add(t)
                t.add_done_callback(self._tasks.discard)
        return started

    async def run_forever(self) -> None:
        try:
            await self.recover()
        except Exception:  # noqa: BLE001
            logger.exception("[functions] 시작 복구 실패")
        while True:
            try:
                await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("[functions] 디스패치 실패")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()

    # ── 한 건 실행 ───────────────────────────────────────────
    async def _finish(self, run_id: str, outcome: RunOutcome, status: Optional[str] = None) -> None:
        values = {
            "status": status or outcome.status, "finished_at": _now(), "exit_code": outcome.exit_code, "error": outcome.error,
            "log": outcome.log or None, "log_truncated": outcome.log_truncated, "duration_ms": outcome.duration_ms, "cold_start_ms": outcome.cold_start_ms,
            "result": json.dumps(outcome.result, ensure_ascii=False) if (outcome.status == "succeeded") else None,
        }
        async with self.session_factory() as db:
            await db.execute(update(FunctionRun).where(FunctionRun.id == run_id).values(**values))
            await db.commit()

    async def execute(self, run_id: str) -> None:
        tmp_path = ""
        cancel = asyncio.Event()
        self._cancel[run_id] = cancel
        poller: Optional[asyncio.Task] = None
        try:
            async with self.session_factory() as db:
                run = await db.get(FunctionRun, run_id, populate_existing=True)
                fn = await db.get(Function, run.function_id)
                ver = (await db.execute(select(FunctionVersion).where(FunctionVersion.function_id == run.function_id, FunctionVersion.version == run.version))).scalar_one_or_none()
                if fn is None or fn.deleted_at is not None or ver is None:
                    return await self._finish(run_id, RunOutcome(status="rejected", error={"type": "Rejected", "message": "함수가 삭제되었거나 버전이 없습니다"}))
                if fn.disabled or run.cancel_requested:
                    msg = "관리자가 함수를 중지했습니다" if fn.disabled else "시작하기 전에 취소되었습니다"
                    return await self._finish(run_id, RunOutcome(status="cancelled" if run.cancel_requested else "rejected", error={"type": "Cancelled" if run.cancel_requested else "Rejected", "message": msg}))
                secrets = await fsvc.load_secrets(db, fn.id)
                cfg, event, user_id = ver.config, (run.input or "{}").encode(), run.user_id
                spec_args = dict(version=ver.version, key=ver.storage_key, tar_bytes=ver.tar_bytes, unpacked=ver.unpacked_bytes, name=fn.name, runtime=fn.runtime)

            fd, tmp_path = tempfile.mkstemp(prefix="fn-pkg-", suffix=".tar.gz")
            with os.fdopen(fd, "wb") as f:
                async for chunk in self.store.stream(spec_args["key"]):
                    f.write(chunk)

            spec = RunSpec(
                run_id=run_id, runtime=spec_args["runtime"], event=event, unpacked_bytes=spec_args["unpacked"], package_path=tmp_path, package_size=spec_args["tar_bytes"],
                function=spec_args["name"], version=str(spec_args["version"]), env={**cfg.get("env", {}), **secrets}, secret_values=list(secrets.values()),
                timeout_s=cfg["timeout_seconds"], memory_mb=cfg["memory_mb"], allow_network=bool(cfg.get("allow_network")),
            )
            async with self.session_factory() as db:
                await db.execute(update(FunctionRun).where(FunctionRun.id == run_id).values(status="running", started_at=_now()))
                await db.commit()

            async def poll_cancel():  # 다른 프로세스·API 가 남긴 취소 요청(cancel_requested)을 본다
                while True:
                    await asyncio.sleep(1.0)
                    async with self.session_factory() as db:
                        flag = (await db.execute(select(FunctionRun.cancel_requested).where(FunctionRun.id == run_id))).scalar()
                    if flag:
                        cancel.set()
                        return

            poller = asyncio.create_task(poll_cancel())
            outcome = await self.runtime.run(spec, cancel)
            await self._finish(run_id, outcome)
        except asyncio.CancelledError:
            await self._finish(run_id, RunOutcome(status="failed", error={"type": "Infrastructure", "message": "서버가 종료되어 실행이 중단되었습니다"}))
            raise
        except Exception as e:  # noqa: BLE001
            logger.exception("[functions] 실행 처리 실패 run=%s", run_id)
            try:
                await self._finish(run_id, RunOutcome(status="failed", error={"type": "Infrastructure", "message": f"{type(e).__name__}: {str(e)[:300]}"}))
            except Exception:  # noqa: BLE001
                logger.exception("[functions] 실패 기록도 실패 run=%s", run_id)
        finally:
            if poller:
                poller.cancel()
            self._cancel.pop(run_id, None)
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            self.kick()  # 자리가 났으니 기다리던 실행을 시작한다

    def cancel_local(self, run_id: str) -> bool:
        ev = self._cancel.get(run_id)
        if ev:
            ev.set()
        return ev is not None

    async def wait_for(self, run_id: str, timeout: float) -> bool:
        """종료 상태가 될 때까지 기다린다 (동기 호출용). 시간 안에 끝났으면 True."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            async with self.session_factory() as db:
                st = (await db.execute(select(FunctionRun.status).where(FunctionRun.id == run_id))).scalar()
            if st in fsvc.TERMINAL:
                return True
            await asyncio.sleep(0.15)
        return False


_dispatcher: Optional[Dispatcher] = None


def get_dispatcher() -> Dispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher()
    return _dispatcher


async def run_function_maintenance() -> None:
    """한 시간마다 보관 기간이 지난 실행 이력과 삭제된 함수를 정리한다."""
    from app.db.session import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                r = await fsvc.purge_expired(db)
                if r["runs"] or r["functions"]:
                    logger.info("[functions] 보관 기간이 지난 실행 %d건, 삭제된 함수 %d개를 영구 삭제했습니다", r["runs"], r["functions"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("[functions] 주기 정리 실패")
        await asyncio.sleep(3600)


async def run_function_scheduler() -> None:
    """예약 트리거를 주기적으로 확인해 실행 시각이 된 것을 큐에 넣고 디스패처를 깨운다."""
    from app.db.session import AsyncSessionLocal
    from app.services import function_trigger_service as tsvc

    while True:
        try:
            async with AsyncSessionLocal() as db:
                if await tsvc.fire_due_schedules(db):
                    get_dispatcher().kick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("[functions] 예약 확인 실패")
        await asyncio.sleep(max(5, settings.SCHEDULER_POLL_SECONDS))

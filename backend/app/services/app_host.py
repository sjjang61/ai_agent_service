"""웹앱 호스트: 앱 레지스트리, 프록시 리스너(20000번대 포트) 관리, 요청 시 깨우기(단일 비행), 유휴 종료.

배포된 앱은 DB(published_apps)에 영속되고, 이 모듈은 그 상태를 메모리에 올려 게이트웨이(app_gateway)가 빠르게 참조하게 한다.
컨테이너가 꺼져 있어도 프록시 포트는 계속 열려 있고, 요청이 오면 아카이브로 새 컨테이너를 만들어 앱을 시작한다.
"""
import asyncio
import contextlib
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
import uvicorn
from sqlalchemy import select

from app.config import settings
from app.models.published_app import PublishedApp
from app.services.app_artifact import STATIC_SERVER_PY

logger = logging.getLogger(__name__)

APP_DIR_LOG = "/workspace/.app.log"
DEPLOY_DIR = "/workspace/deploy"


class AppError(Exception):
    pass


@dataclass
class AppState:
    id: str
    user_id: str
    name: str
    kind: str
    port: Optional[int]
    container_port: int
    require_token: bool
    token: str
    status: str = "stopped"
    error: Optional[str] = None
    container_id: Optional[str] = None
    upstream: Optional[int] = None  # 컨테이너 앱 포트가 게시된 호스트(loopback) 포트
    version: int = 1
    retry_count: int = 0
    failed_at: float = 0.0
    last_touch: float = field(default_factory=time.monotonic)
    last_db_touch: float = 0.0


def pick_port(used: set, start: int, end: int, is_free=lambda p: True) -> Optional[int]:
    """start~end(포함) 중 used 에 없고 실제로 바인드 가능한 가장 낮은 포트. 없으면 None."""
    for p in range(start, end + 1):
        if p not in used and is_free(p):
            return p
    return None


def port_is_free(port: int, host: Optional[str] = None) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host or settings.APP_BIND_HOST, port))
            return True
        except OSError:
            return False


def app_dir(app_id: str) -> str:
    return os.path.join(settings.APP_DATA_DIR, app_id)


def artifact_path(app_id: str) -> str:
    return os.path.join(app_dir(app_id), "artifact.tar.gz")


def data_path(app_id: str) -> str:
    return os.path.join(app_dir(app_id), "data")


class _QuietServer(uvicorn.Server):
    """메인 서버의 SIGINT/SIGTERM 처리를 가로채지 않는 uvicorn 서버 (앱 프록시 리스너용)."""

    def install_signal_handlers(self) -> None:  # 구버전 uvicorn
        return

    @contextlib.contextmanager
    def capture_signals(self):  # 신버전 uvicorn
        yield


class AppHost:
    def __init__(self):
        self.states: dict[str, AppState] = {}
        self._servers: dict[str, tuple[_QuietServer, asyncio.Task]] = {}
        self._wake: dict[str, asyncio.Task] = {}

    # ── 레지스트리 ────────────────────────────────────────────────────────────
    @staticmethod
    def _manager():
        from app.services.sandbox_service import sandbox_manager

        return sandbox_manager

    def register(self, rec: PublishedApp) -> AppState:
        st = self.states.get(rec.id)
        if st is None:
            st = AppState(id=rec.id, user_id=rec.user_id, name=rec.name, kind=rec.kind, port=rec.proxy_port,
                          container_port=rec.container_port, require_token=bool(rec.require_token), token=rec.access_token)
            self.states[rec.id] = st
        st.name, st.kind, st.port = rec.name, rec.kind, rec.proxy_port
        st.container_port, st.require_token, st.token, st.version = rec.container_port, bool(rec.require_token), rec.access_token, rec.version
        return st

    async def _persist(self, app_id: str, **fields):
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            rec = await db.get(PublishedApp, app_id)
            if rec:
                for k, v in fields.items():
                    setattr(rec, k, v)
                await db.commit()

    async def load(self):
        """시작 시: DB 의 모든 앱을 올리고 프록시 리스너를 연다. 컨테이너가 살아 있으면 이어서 쓰고, 아니면 stopped 로 둔다."""
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            recs = (await db.execute(select(PublishedApp))).scalars().all()
        for rec in recs:
            st = self.register(rec)
            st.error, st.retry_count = rec.error, rec.retry_count or 0
            up = await self._manager().published_port(rec.container_id, rec.container_port) if rec.container_id else None
            if up and rec.status == "running":
                st.status, st.upstream, st.container_id = "running", up, rec.container_id
            else:
                st.status, st.upstream = ("failed" if rec.status == "failed" else "stopped"), None
                if rec.status in ("running", "starting"):
                    await self._persist(rec.id, status="stopped", container_id=None)
            if st.port:
                await self.ensure_listener(st)
        logger.info("[apps] %d개 앱 로드, 리스너 %d개", len(recs), len(self._servers))

    # ── 프록시 리스너 ─────────────────────────────────────────────────────────
    async def ensure_listener(self, st: AppState):
        if not st.port or st.id in self._servers:
            return
        from app.services.app_gateway import make_gateway

        cfg = uvicorn.Config(make_gateway(self, st.id), host=settings.APP_BIND_HOST, port=st.port, log_config=None,
                             access_log=False, lifespan="off", ws="websockets", timeout_keep_alive=30)
        server = _QuietServer(cfg)

        async def run():
            try:
                await server.serve()
            except SystemExit:  # uvicorn 은 바인드 실패 시 sys.exit 한다
                logger.error("[apps] 포트 %s 를 열지 못했습니다 (앱 %s)", st.port, st.name)
                st.status, st.error = "failed", f"프록시 포트 {st.port} 를 열지 못했습니다 (다른 프로세스가 사용 중일 수 있습니다)"
            except Exception:  # noqa: BLE001
                logger.exception("[apps] 리스너 오류 (포트 %s)", st.port)

        self._servers[st.id] = (server, asyncio.create_task(run()))

    async def stop_listener(self, app_id: str):
        entry = self._servers.pop(app_id, None)
        if entry:
            server, task = entry
            server.should_exit = True
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task, 5)
            if not task.done():
                task.cancel()

    async def shutdown(self):
        """서버 종료: 리스너만 닫는다. 컨테이너는 그대로 두어 다음 시작 때 이어서 쓴다."""
        for t in self._wake.values():
            t.cancel()
        await asyncio.gather(*(self.stop_listener(i) for i in list(self._servers)), return_exceptions=True)

    # ── 깨우기 ────────────────────────────────────────────────────────────────
    def wake(self, app_id: str) -> asyncio.Task:
        """앱을 시작한다 (같은 앱의 동시 요청은 하나의 시작을 공유). Task 결과: 준비되면 True."""
        t = self._wake.get(app_id)
        if t and not t.done():
            return t
        t = asyncio.create_task(self._wake_guarded(app_id))
        self._wake[app_id] = t
        return t

    def touch(self, st: AppState):
        now = time.monotonic()
        st.last_touch = now
        if now - st.last_db_touch > 30:
            st.last_db_touch = now
            from datetime import datetime

            asyncio.create_task(self._persist(st.id, last_request_at=datetime.utcnow()))

    def cooldown_message(self, st: AppState) -> Optional[str]:
        """최근에 실패했다면 재시도 전 안내 문구 (쿨다운 중이거나 재시도 한도를 넘었을 때)."""
        if st.status != "failed":
            return None
        if st.retry_count >= settings.APP_MAX_RETRIES:
            return f"시작에 {st.retry_count}번 실패했습니다. 문제를 고친 뒤 다시 배포하거나 수동으로 시작하세요.\n{st.error or ''}"
        left = settings.APP_FAILURE_COOLDOWN - (time.monotonic() - st.failed_at)
        if left > 0:
            return f"시작에 실패했습니다. {int(left) + 1}초 뒤 다시 시도합니다.\n{st.error or ''}"
        return None

    async def _wake_guarded(self, app_id: str) -> bool:
        st = self.states.get(app_id)
        if not st:
            return False
        if self.cooldown_message(st):
            return False
        try:
            await self._start(st)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            msg = str(e) or type(e).__name__
            logger.warning("[apps] %s 시작 실패: %s", st.name, msg[:300])
            st.status, st.error, st.upstream = "failed", msg[:3000], None
            st.retry_count += 1
            st.failed_at = time.monotonic()
            await self._persist(st.id, status="failed", error=st.error, retry_count=st.retry_count, container_id=None)
            return False

    async def _http_ready(self, port: int) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2) as c:
                await c.get(f"http://127.0.0.1:{port}/")
            return True  # 404 등 어떤 HTTP 응답이든 서버가 떠 있다는 뜻
        except httpx.HTTPError:
            return False

    async def _log_tail(self, container_id: str, n: int = 4000) -> str:
        try:
            code, out, _ = await self._manager().exec_command(container_id, f"tail -c {n} {APP_DIR_LOG} 2>/dev/null", timeout=10)
            return out.strip()
        except Exception:  # noqa: BLE001
            return ""

    async def _start(self, st: AppState):
        mgr = self._manager()
        st.status, st.error = "starting", None
        await self._persist(st.id, status="starting", error=None)
        if st.container_id:  # 남은 컨테이너가 있으면 정리하고 새로 만든다
            await mgr.destroy_sandbox(st.container_id)
            st.container_id = None
        art = artifact_path(st.id)
        if not os.path.exists(art):
            raise AppError("배포 아카이브가 없습니다. 다시 배포하세요.")
        image = settings.APP_IMAGE or settings.SANDBOX_IMAGE
        cid, host_port = await mgr.create_app_container(st.id, st.user_id, st.container_port, data_path(st.id), image,
                                                       settings.APP_MEMORY_LIMIT, settings.APP_CPU_LIMIT, settings.APP_BIND_HOST)
        st.container_id = cid
        try:
            await mgr.put_archive_file(cid, art, DEPLOY_DIR)
            if st.kind == "server":
                script = f"{DEPLOY_DIR}/.scripts/start.sh"
                code, _, _ = await mgr.exec_command(cid, f"test -f {script}", timeout=10)
                if code != 0:
                    raise AppError("아카이브에 .scripts/start.sh 가 없습니다")
                cmd = f"cd {DEPLOY_DIR} && bash .scripts/start.sh"
            else:
                await mgr.write_file(cid, "/workspace/.static_server.py", STATIC_SERVER_PY.encode())
                cmd = f"python3 /workspace/.static_server.py {st.container_port} {DEPLOY_DIR}"
            await mgr.exec_detached(cid, f"{cmd} > {APP_DIR_LOG} 2>&1", env={"PORT": str(st.container_port), "DATA_DIR": "/workspace/data", "HOST": "0.0.0.0"})
            deadline = time.monotonic() + settings.APP_STARTUP_TIMEOUT
            while time.monotonic() < deadline:
                await asyncio.sleep(0.5)
                if not await mgr.is_running(cid):
                    raise AppError("컨테이너가 시작 직후 종료되었습니다\n" + await self._log_tail(cid))
                if await self._http_ready(host_port):
                    break
            else:
                raise AppError(f"{settings.APP_STARTUP_TIMEOUT}초 안에 앱이 응답하지 않았습니다 (포트 {st.container_port} 에서 0.0.0.0 으로 듣고 있는지 확인하세요)\n" + await self._log_tail(cid))
        except BaseException:
            with contextlib.suppress(Exception):
                tail = await self._log_tail(cid)
                await self._persist(st.id, last_log=tail or None)
                await mgr.destroy_sandbox(cid)
            st.container_id = None
            raise
        st.status, st.upstream, st.error, st.retry_count = "running", host_port, None, 0
        st.last_touch = time.monotonic()
        await self._persist(st.id, status="running", container_id=cid, error=None, retry_count=0)
        logger.info("[apps] %s 시작 (프록시 %s → 컨테이너 %s:%s)", st.name, st.port, host_port, st.container_port)

    # ── 중지 ──────────────────────────────────────────────────────────────────
    async def stop_container(self, st: AppState, status: str = "stopped"):
        t = self._wake.get(st.id)
        if t and not t.done():
            t.cancel()
            with contextlib.suppress(BaseException):
                await t
        log = None
        if st.container_id:
            log = await self._log_tail(st.container_id)
            await self._manager().destroy_sandbox(st.container_id)
        st.container_id, st.upstream, st.status = None, None, status
        await self._persist(st.id, status=status, container_id=None, last_log=log or None)

    async def reap_idle(self):
        limit = settings.APP_IDLE_MINUTES * 60
        for st in list(self.states.values()):
            if st.status == "running" and time.monotonic() - st.last_touch > limit:
                logger.info("[apps] 유휴 종료: %s", st.name)
                try:
                    await self.stop_container(st)
                except Exception:  # noqa: BLE001
                    logger.exception("[apps] 유휴 종료 실패: %s", st.name)

    async def remove(self, app_id: str):
        st = self.states.pop(app_id, None)
        await self.stop_listener(app_id)
        if st:
            t = self._wake.pop(app_id, None)
            if t and not t.done():
                t.cancel()
            if st.container_id:
                await self._manager().destroy_sandbox(st.container_id)


host = AppHost()


async def run_app_reaper():
    """유휴 앱 컨테이너를 주기적으로 내리는 백그라운드 루프."""
    while True:
        try:
            await asyncio.sleep(60)
            await host.reap_idle()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("[apps] reaper 오류")

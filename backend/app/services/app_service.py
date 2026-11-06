"""웹앱 배포 서비스: sandbox 의 빌드 결과(디렉터리)를 불변 아카이브로 저장하고 포트를 배정해 앱으로 등록한다."""
import asyncio
import os
import re
import secrets
import shutil
import tempfile
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.published_app import PublishedApp
from app.services.app_artifact import ArtifactError, normalize_archive
from app.services.app_host import APP_DIR_LOG, app_dir, artifact_path, data_path, host, pick_port, port_is_free

_NAME_RE = re.compile(r"^[0-9A-Za-z가-힣][0-9A-Za-z가-힣 _.\-]{0,59}$")
_alloc_lock = asyncio.Lock()
MB = 1024 * 1024


class DeployError(Exception):
    pass


def app_url(rec: PublishedApp, with_token: bool = True) -> Optional[str]:
    if not rec.proxy_port:
        return None
    url = f"http://{settings.APP_PUBLIC_HOST}:{rec.proxy_port}/"
    return url + (f"?t={rec.access_token}" if with_token and rec.require_token else "")


class AppService:
    @staticmethod
    async def list_for_user(user_id: str, db: AsyncSession) -> list:
        r = await db.execute(select(PublishedApp).where(PublishedApp.user_id == user_id).order_by(PublishedApp.created_at.desc()))
        return list(r.scalars().all())

    @staticmethod
    async def get(user_id: str, app_id_or_name: str, db: AsyncSession) -> Optional[PublishedApp]:
        r = await db.execute(select(PublishedApp).where(PublishedApp.user_id == user_id, (PublishedApp.id == app_id_or_name) | (PublishedApp.name == app_id_or_name)))
        return r.scalars().first()

    @staticmethod
    def live(rec: PublishedApp) -> PublishedApp:
        """레지스트리의 최신 상태를 응답용 레코드에 덮어쓴다 (DB 는 일부 변경을 늦게 반영한다)."""
        st = host.states.get(rec.id)
        if st:
            rec.status, rec.error = st.status, st.error
        return rec

    @staticmethod
    async def deploy(user_id: str, db: AsyncSession, conversation_id: Optional[str], name: str, path: str, kind: str = "auto", private: Optional[bool] = None) -> PublishedApp:
        from app.services.sandbox_service import SandboxService, sandbox_manager
        from app.tools.workspace_tools import resolve_path

        name = " ".join((name or "").split())
        if not _NAME_RE.match(name):
            raise DeployError("앱 이름은 한글·영문·숫자·공백·_.- 만 쓸 수 있고 60자 이내여야 합니다")
        try:
            full = resolve_path(path)
        except ValueError as e:
            raise DeployError(str(e))
        existing = await AppService.get(user_id, name, db)
        if existing is None:
            count = len(await AppService.list_for_user(user_id, db))
            if count >= settings.APP_MAX_PER_USER:
                raise DeployError(f"배포할 수 있는 앱은 최대 {settings.APP_MAX_PER_USER}개입니다. 안 쓰는 앱을 삭제하세요")

        sb = await SandboxService.get_or_create_sandbox(user_id, db, conversation_id or None)
        cid = sb.container_id

        async def test(flag: str, p: str) -> bool:
            code, _, _ = await sandbox_manager.exec_command(cid, f"test {flag} {_q(p)}", timeout=15)
            return code == 0

        if not await test("-d", full):
            raise DeployError(f"디렉터리가 없습니다: {path} (빌드 결과 디렉터리를 지정하세요. 예: dist)")
        has_start = await test("-f", f"{full}/.scripts/start.sh")
        has_index = await test("-f", f"{full}/index.html")
        if kind == "auto":
            kind = "server" if has_start else "static"
        if kind == "server" and not has_start:
            raise DeployError(f"서버형 앱은 {path}/.scripts/start.sh 가 필요합니다. 이 스크립트가 0.0.0.0:$PORT 에서 서버를 시작해야 합니다 (데이터는 $DATA_DIR 에 저장)")
        if kind == "static" and not has_index:
            raise DeployError(f"{path}/index.html 이 없습니다. 정적 앱은 빌드 결과(index.html 포함)를 가리켜야 합니다 (서버형이면 .scripts/start.sh 를 만드세요)")
        if kind not in ("static", "server"):
            raise DeployError("kind 는 auto, static, server 중 하나여야 합니다")

        # 아카이브: 컨테이너에서 꺼내 검증·정규화한 뒤 앱 디렉터리에 저장
        tmp_dir = tempfile.mkdtemp(prefix="appdeploy-")
        try:
            raw = os.path.join(tmp_dir, "raw.tar")
            max_bytes = settings.APP_ARTIFACT_MAX_MB * MB
            try:
                await sandbox_manager.export_path(cid, full, raw, max_bytes * 2)
            except RuntimeError as e:
                raise DeployError(str(e))
            out = os.path.join(tmp_dir, "artifact.tar.gz")
            loop = asyncio.get_running_loop()
            try:
                files, total = await loop.run_in_executor(None, normalize_archive, raw, out, max_bytes, settings.APP_ARTIFACT_MAX_FILES)
            except ArtifactError as e:
                raise DeployError(str(e))

            async with _alloc_lock:
                rec = await AppService.get(user_id, name, db)
                if rec is None:
                    used = set((await db.execute(select(PublishedApp.proxy_port).where(PublishedApp.proxy_port.is_not(None)))).scalars().all())
                    port = pick_port(used, settings.APP_PORT_START, settings.APP_PORT_END, is_free=port_is_free)
                    if port is None:
                        raise DeployError(f"사용할 수 있는 포트가 없습니다 ({settings.APP_PORT_START}~{settings.APP_PORT_END}). 안 쓰는 앱을 삭제하세요")
                    rec = PublishedApp(user_id=user_id, name=name, kind=kind, proxy_port=port, container_port=settings.APP_CONTAINER_PORT,
                                       access_token=secrets.token_urlsafe(24), require_token=settings.APP_REQUIRE_TOKEN if private is None else bool(private))
                    db.add(rec)
                else:
                    rec.version += 1
                    rec.kind = kind
                    if private is not None:
                        rec.require_token = bool(private)
                rec.conversation_id = conversation_id or rec.conversation_id
                rec.artifact_size = os.path.getsize(out)
                rec.error, rec.retry_count = None, 0
                try:
                    await db.commit()
                except IntegrityError:
                    await db.rollback()
                    raise DeployError("앱 등록 중 충돌이 발생했습니다. 다시 시도하세요")
                await db.refresh(rec)
            os.makedirs(data_path(rec.id), exist_ok=True)
            shutil.move(out, artifact_path(rec.id))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        st = host.register(rec)
        st.retry_count, st.failed_at = 0, 0.0
        if st.status != "stopped":
            await host.stop_container(st)  # 새 버전으로 교체: 다음 시작에 새 아카이브를 쓴다
        st.status, st.error = "stopped", None
        await host.ensure_listener(st)
        ok = False
        try:
            ok = await asyncio.wait_for(asyncio.shield(host.wake(rec.id)), settings.APP_STARTUP_TIMEOUT + 15)
        except Exception:  # noqa: BLE001
            pass
        await db.refresh(rec)
        return AppService.live(rec)

    @staticmethod
    async def start(rec: PublishedApp) -> bool:
        st = host.states.get(rec.id)
        if not st:
            return False
        st.retry_count, st.failed_at = 0, 0.0
        if st.status == "failed":
            st.status = "stopped"
        await host.ensure_listener(st)
        return bool(await host.wake(rec.id))

    @staticmethod
    async def stop(rec: PublishedApp):
        st = host.states.get(rec.id)
        if st:
            await host.stop_container(st)

    @staticmethod
    async def delete(rec: PublishedApp, db: AsyncSession):
        await host.remove(rec.id)
        await db.delete(rec)
        await db.commit()
        shutil.rmtree(app_dir(rec.id), ignore_errors=True)

    @staticmethod
    async def logs(rec: PublishedApp, lines: int = 100) -> str:
        st = host.states.get(rec.id)
        if st and st.container_id:
            try:
                _, out, _ = await host._manager().exec_command(st.container_id, f"tail -n {int(max(1, min(lines, 500)))} {APP_DIR_LOG} 2>/dev/null", timeout=10)
                if out.strip():
                    return out
            except Exception:  # noqa: BLE001
                pass
        return rec.last_log or ""


def _q(p: str) -> str:
    import shlex

    return shlex.quote(p)

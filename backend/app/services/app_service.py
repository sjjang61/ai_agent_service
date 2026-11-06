"""웹앱 배포 서비스: sandbox 의 빌드 결과(디렉터리)를 불변 아카이브로 저장하고 포트를 배정해 앱으로 등록한다."""
import asyncio
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.published_app import AppReport, PublishedApp
from app.models.user import User
from app.services import app_auth
from app.services.app_artifact import ArtifactError, normalize_archive
from app.services.app_policy import CATEGORIES, decide_publish, make_slug, public_url, scan_artifact
from app.services.app_host import APP_DIR_LOG, app_dir, artifact_path, data_path, host, pick_port, port_is_free

_NAME_RE = re.compile(r"^[0-9A-Za-z가-힣][0-9A-Za-z가-힣 _.\-]{0,59}$")
_alloc_lock = asyncio.Lock()
MB = 1024 * 1024


class DeployError(Exception):
    pass


class PublishError(Exception):
    pass


def is_public(rec: PublishedApp) -> bool:
    return rec.visibility == "public" and rec.moderation_status == "approved"


def app_url(rec: PublishedApp) -> Optional[str]:
    """화면 표시용 주소. 공개(승인)된 앱은 호스트명 주소, 비공개 앱은 포트 주소(소유자 실행 티켓이 있어야 열린다)."""
    if is_public(rec) and rec.slug:
        return public_url(rec.slug)
    return f"http://{settings.APP_PUBLIC_HOST}:{rec.proxy_port}/" if rec.proxy_port else None


def launch_url(rec: PublishedApp, user_id: str) -> str:
    """접속 주소. 공개 앱은 그대로, 비공개 앱은 소유자 본인에게만 일회용 실행 티켓(60초)을 붙여 준다."""
    if is_public(rec) and rec.slug:
        return public_url(rec.slug)
    if rec.user_id != user_id:
        raise PermissionError("소유자만 열 수 있는 앱입니다")
    return f"http://{settings.APP_PUBLIC_HOST}:{rec.proxy_port}/?t={app_auth.make_ticket(rec.id, user_id)}"


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
        """private 인자는 호환용이다 (새 앱은 항상 비공개로 시작하고 App Store 등록으로만 공개된다)."""
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
                                       access_token=secrets.token_urlsafe(24), visibility="private", moderation_status="")
                    db.add(rec)
                    await db.flush()
                    rec.slug = make_slug(name, rec.id)
                else:
                    rec.version += 1
                    rec.kind = kind
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
            if rec.visibility == "public":  # 공개 중인 앱을 새 버전으로 바꾸면 다시 점검한다
                await AppService._recheck_public(rec, db)
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

    # ── 공개(App Store) ───────────────────────────────────────────────────────
    @staticmethod
    async def _scan(rec: PublishedApp) -> list:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, scan_artifact, artifact_path(rec.id))

    @staticmethod
    async def _recheck_public(rec: PublishedApp, db: AsyncSession):
        """공개 중인 앱의 새 버전 점검: 걸리면 비공개로 되돌리고, 정적 앱은 승인 유지, 서버형은 다시 승인 대기."""
        status, note = decide_publish(rec.kind, await AppService._scan(rec))
        if status == "blocked":
            rec.visibility, rec.moderation_status, rec.listed_at = "private", "", None
            rec.moderation_note = f"새 버전 점검에서 공개가 해제되었습니다: {note}"
        else:
            rec.moderation_status, rec.moderation_note = status, note or None
        await db.commit()

    @staticmethod
    def _clean_listing(title: str, description: str, category: Optional[str], tags) -> tuple:
        title = " ".join((title or "").split())[:100]
        if not title:
            raise PublishError("제목을 입력하세요")
        description = (description or "").strip()[:2000]
        category = category if category in CATEGORIES else "other"
        clean = []
        for t in tags or []:
            t = " ".join(str(t).split())[:20]
            if t and t not in clean:
                clean.append(t)
        return title, description, category, clean[:8]

    @staticmethod
    async def publish(rec: PublishedApp, db: AsyncSession, title: str, description: str, category: Optional[str], tags) -> PublishedApp:
        """App Store 에 등록한다. 점검(비밀 파일·키 탐지)에 걸리면 거부, 정적 앱은 즉시 공개, 서버형 앱은 관리자 승인 대기."""
        title, description, category, tags = AppService._clean_listing(title, description, category, tags)
        if not os.path.exists(artifact_path(rec.id)):
            raise PublishError("배포 아카이브가 없습니다. 다시 배포한 뒤 등록하세요")
        status, note = decide_publish(rec.kind, await AppService._scan(rec))
        if status == "blocked":
            raise PublishError(f"공개할 수 없습니다: {note}")
        rec.visibility, rec.moderation_status, rec.moderation_note = "public", status, note or None
        rec.title, rec.description, rec.category, rec.tags = title, description, category, tags
        rec.listed_at = datetime.utcnow() if status == "approved" else None
        await db.commit()
        await db.refresh(rec)
        host.register(rec)
        return rec

    @staticmethod
    async def update_listing(rec: PublishedApp, db: AsyncSession, title: str, description: str, category: Optional[str], tags) -> PublishedApp:
        title, description, category, tags = AppService._clean_listing(title, description, category, tags)
        rec.title, rec.description, rec.category, rec.tags = title, description, category, tags
        await db.commit()
        await db.refresh(rec)
        return rec

    @staticmethod
    async def unpublish(rec: PublishedApp, db: AsyncSession) -> PublishedApp:
        """비공개로 되돌린다: 익명 접속은 즉시 막히고 스토어 목록에서 빠진다 (데이터는 보존)."""
        rec.visibility, rec.moderation_status, rec.moderation_note, rec.listed_at = "private", "", None, None
        await db.commit()
        await db.refresh(rec)
        host.register(rec)
        return rec

    @staticmethod
    async def moderate(rec: PublishedApp, db: AsyncSession, action: str, note: Optional[str]) -> PublishedApp:
        """관리자 처리: approve(공개 승인) | reject(반려, 비공개로) | suspend(정지, 서비스 중단)."""
        if action == "approve":
            if rec.visibility != "public":
                raise PublishError("공개를 요청한 앱만 승인할 수 있습니다")
            rec.moderation_status, rec.moderation_note = "approved", note
            rec.listed_at = rec.listed_at or datetime.utcnow()
        elif action == "reject":
            rec.visibility, rec.moderation_status, rec.moderation_note, rec.listed_at = "private", "rejected", note, None
        elif action == "suspend":
            rec.moderation_status, rec.moderation_note = "suspended", note
        else:
            raise PublishError("알 수 없는 처리입니다")
        await db.commit()
        await db.refresh(rec)
        st = host.register(rec)
        if action == "suspend":
            await host.stop_container(st)  # 정지된 앱의 컨테이너는 바로 내린다
        return rec

    @staticmethod
    async def report(rec: PublishedApp, reporter_id: str, reason: str, db: AsyncSession) -> int:
        """공개 앱 신고. 서로 다른 사용자의 신고가 임계치에 이르면 자동 정지(검수 대기)한다. 반환: 누적 신고 수."""
        reason = (reason or "").strip()[:1000]
        if not reason:
            raise PublishError("신고 사유를 입력하세요")
        if not (await db.execute(select(AppReport.id).where(AppReport.app_id == rec.id, AppReport.reporter_id == reporter_id))).first():
            db.add(AppReport(app_id=rec.id, reporter_id=reporter_id, reason=reason))
            await db.commit()
        count = (await db.execute(select(func.count()).select_from(AppReport).where(AppReport.app_id == rec.id))).scalar() or 0
        if count >= settings.APP_REPORT_SUSPEND_THRESHOLD and rec.moderation_status == "approved":
            await AppService.moderate(rec, db, "suspend", f"신고 {count}건이 접수되어 자동 정지되었습니다. 관리자 검토가 필요합니다")
        return count

    @staticmethod
    async def store_list(db: AsyncSession, q: Optional[str], category: Optional[str], sort: str, limit: int, offset: int) -> list:
        """공개(승인)된 앱 목록과 소유자 표시명. sort: popular(접속 수) | new(등록 순)."""
        query = select(PublishedApp, User.display_name).join(User, User.id == PublishedApp.user_id).where(
            PublishedApp.visibility == "public", PublishedApp.moderation_status == "approved")
        if category:
            query = query.where(PublishedApp.category == category)
        if q:
            like = f"%{q}%"
            query = query.where((PublishedApp.title.ilike(like)) | (PublishedApp.description.ilike(like)) | (PublishedApp.name.ilike(like)))
        query = query.order_by(PublishedApp.launch_count.desc() if sort == "popular" else PublishedApp.listed_at.desc()).limit(limit).offset(offset)
        return list((await db.execute(query)).all())

    @staticmethod
    async def count_launch(app_id: str):
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            rec = await db.get(PublishedApp, app_id)
            if rec:
                rec.launch_count = (rec.launch_count or 0) + 1
                await db.commit()

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

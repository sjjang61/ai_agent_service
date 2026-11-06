"""웹앱 배포 도구: deploy_web_app(빌드 결과를 외부 접속 URL 로 배포), manage_web_app(목록·상태·시작·중지·삭제·로그)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.tools.workspace_tools import _AsyncTool, _fmt_err


class DeployInput(BaseModel):
    path: str = Field(description="Directory in the workspace to deploy: the build output (e.g. dist, build, out) for a static app, or the app directory that contains .scripts/start.sh for a server app")
    name: str = Field(description="App name (letters, digits, spaces, _ . -; max 60). Deploying with an existing name updates that app in place and keeps its URL")
    kind: Literal["auto", "static", "server"] = Field(default="auto", description="auto: server if <path>/.scripts/start.sh exists, otherwise static. static needs <path>/index.html")
    private: Optional[bool] = Field(default=None, description="Ignored. Deployed apps are always private (owner only) until the user publishes them in the App Store")


class DeployWebAppTool(_AsyncTool):
    name: str = "deploy_web_app"
    description: str = (
        "Deploy a web app built in the workspace so the user can open it in a browser (private to the owner; shown in the chat preview panel and in My Apps). "
        "The directory is archived (immutable snapshot) and served from a dedicated lightweight container on its own port; "
        "the container sleeps when idle and wakes automatically on the next request, so the URL stays stable. "
        "STATIC app: pass the build output directory (must contain index.html; single-page-app routing works; the app is served at the URL root, so the default Vite base '/' is fine). "
        "SERVER app (API server, Node/Python backend, full-stack): the directory must contain a bash script .scripts/start.sh that starts the server "
        "listening on 0.0.0.0:$PORT (the PORT env var is always set); persistent data (SQLite etc.) must be written under $DATA_DIR, which survives restarts. "
        "The archive must be self-contained (include node_modules/ or build output; there is no network install at wake time unless start.sh does it). "
        "Max size and file count are limited. Re-run this tool with the same name after rebuilding to publish a new version. "
        "The app opens in the preview panel automatically; tell the user the first request after idle may take a few seconds."
    )
    args_schema: type[BaseModel] = DeployInput

    async def _arun(self, path: str, name: str, kind: str = "auto", private: Optional[bool] = None) -> str:
        if not settings.APP_HOST_ENABLED:
            return "Error: 웹앱 배포 기능이 꺼져 있습니다 (APP_HOST_ENABLED)"
        from app.db.session import AsyncSessionLocal
        from app.services.app_service import AppService, DeployError, app_url

        try:
            async with AsyncSessionLocal() as db:
                rec = await AppService.deploy(self.user_id, db, self.sandbox_cid or None, name, path, kind, private)
                if rec.status != "running":
                    logs = await AppService.logs(rec, 40)
                    return f"Error: 배포는 저장되었지만 앱을 시작하지 못했습니다 ({rec.kind}). {rec.error or ''}\n--- log ---\n{logs}"
                return (f"Deployed '{rec.name}' (v{rec.version}, {rec.kind}). App ID: {rec.id}\n"
                        f"The app is private (owner only). Tell the user to open it from the My Apps menu or the app preview panel; the user can register it in the App Store to make it public. "
                        f"Do not hand out the port URL as a link — it needs the owner's session. It sleeps after {settings.APP_IDLE_MINUTES} min without requests and wakes on the next request.")
        except DeployError as e:
            return f"Error: {e}"
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)


class ManageInput(BaseModel):
    action: Literal["list", "status", "start", "stop", "delete", "logs"] = Field(description="list: all my deployed apps; status/start/stop/delete/logs: need name")
    name: Optional[str] = Field(default=None, description="App name (not needed for list)")


class ManageWebAppTool(_AsyncTool):
    name: str = "manage_web_app"
    description: str = (
        "Manage web apps deployed with deploy_web_app: list them, check status, start/stop the container, delete an app (frees its port and data), "
        "or read the latest app log (use logs when an app fails to start or returns errors)."
    )
    args_schema: type[BaseModel] = ManageInput

    async def _arun(self, action: str, name: Optional[str] = None) -> str:
        from app.db.session import AsyncSessionLocal
        from app.services.app_service import AppService, app_url, is_public

        def where(r) -> str:
            return f"public {app_url(r)}" if is_public(r) else "private (open from My Apps)"

        try:
            async with AsyncSessionLocal() as db:
                if action == "list":
                    recs = await AppService.list_for_user(self.user_id, db)
                    if not recs:
                        return "배포된 앱이 없습니다."
                    return "\n".join(f"- {AppService.live(r).name} [{r.status}] {r.kind} v{r.version} {where(r)}" for r in recs)
                if not name:
                    return "Error: name 이 필요합니다"
                rec = await AppService.get(self.user_id, name, db)
                if not rec:
                    return f"Error: '{name}' 앱을 찾을 수 없습니다"
                if action == "status":
                    AppService.live(rec)
                    return f"{rec.name}: {rec.status} ({rec.kind} v{rec.version}) {where(rec)}" + (f"\n{rec.error}" if rec.error else "")
                if action == "start":
                    ok = await AppService.start(rec)
                    await db.refresh(rec)
                    return f"{rec.name}: {'running' if ok else 'failed'} {where(rec)}" + ("" if ok else f"\n{AppService.live(rec).error or ''}")
                if action == "stop":
                    await AppService.stop(rec)
                    return f"{rec.name}: stopped (다음 요청에 다시 깨어납니다)"
                if action == "delete":
                    await AppService.delete(rec, db)
                    return f"{name}: deleted"
                if action == "logs":
                    return (await AppService.logs(rec, 100)) or "(로그 없음)"
                return "Error: 알 수 없는 action"
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)

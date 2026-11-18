"""Functions API: Drive 의 zip 으로 등록, 버전·별칭·시크릿, 동기/비동기 호출, 이력·로그·취소, 관리자 스위치, 접근 제어"""
import asyncio
import hashlib
import io
import json
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.dependencies import get_current_user
from app.main import app
from app.models.drive import DriveNode, DriveUsage
from app.models.function import Function, FunctionAlias, FunctionRun, FunctionSecret, FunctionTrigger, FunctionVersion
from app.models.user import User
from app.services import drive_service, drive_storage
from app.services.function_dispatcher import Dispatcher
from app.services.function_package import build_zip
from app.services.function_runtime import RunOutcome
from tests.unit.test_drive_service import MemStore
from tests.unit.test_function_service import FakeRuntime

A = SimpleNamespace(id="user-a-0000", email="a@x.com")
B = SimpleNamespace(id="user-b-0000", email="b@x.com")
ADMIN = SimpleNamespace(id="admin-0000", email="boss@x.com")
CURRENT = {"user": A}
CFG = {"runtime": "python3.12", "handler": "main.handler"}


def good_zip(ret=1):
    return build_zip({"function.json": json.dumps(CFG), "main.py": f"def handler(e, c): return {ret}\n"})


@pytest_asyncio.fixture
async def ctx(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/api.db", connect_args={"timeout": 30})
    tables = [t.__table__ for t in (Function, FunctionVersion, FunctionAlias, FunctionSecret, FunctionRun, FunctionTrigger, DriveNode, DriveUsage, User)]
    async with engine.begin() as c:
        await c.run_sync(lambda conn: Base.metadata.create_all(conn, tables=tables))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as seed:
        for u in (A, B, ADMIN):
            seed.add(User(id=u.id, email=u.email, hashed_password="x", display_name=u.email, is_active=True))
        await seed.commit()
    store = MemStore()
    monkeypatch.setattr(drive_storage, "storage", store)
    monkeypatch.setattr(drive_storage, "enabled", lambda: True)
    for k, v in {"FUNCTION_ENABLED": True, "FUNCTION_ALLOWED_EMAILS": "*", "ADMIN_EMAILS": "boss@x.com", "MINIO_ENDPOINT": "x", "MINIO_ACCESS_KEY": "x", "MINIO_SECRET_KEY": "x"}.items():
        monkeypatch.setattr(settings, k, v)
    rt = FakeRuntime()
    disp = Dispatcher(runtime=rt, store=store, session_factory=maker)
    monkeypatch.setattr("app.api.functions.get_dispatcher", lambda: disp)

    async def session_dep():
        async with maker() as s:
            yield s

    CURRENT["user"] = A
    app.dependency_overrides[get_session] = session_dep
    app.dependency_overrides[get_current_user] = lambda: CURRENT["user"]
    loop = asyncio.create_task(disp.run_forever())
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield SimpleNamespace(c=c, maker=maker, store=store, rt=rt, disp=disp)
    loop.cancel()
    for t in list(disp._tasks):  # 남은 실행 작업이 DB 를 쓰는 채로 엔진을 닫으면 SQLite 워커 스레드가 끝나지 않는다
        t.cancel()
    await asyncio.gather(loop, *disp._tasks, return_exceptions=True)
    app.dependency_overrides.clear()
    await engine.dispose()


async def put_zip(ctx, user, name="pkg.zip", data=None):
    """Drive 에 zip 을 올려 노드 id 를 돌려준다."""
    data = data if data is not None else good_zip()
    async with ctx.maker() as db:
        node = await drive_service.create_file(db, user.id, "root", name, io.BytesIO(data), len(data), hashlib.sha256(data).hexdigest(), store=ctx.store)
    return node.id


async def create(ctx, name="hello", user=A, data=None):
    nid = await put_zip(ctx, user, data=data)
    CURRENT["user"] = user
    return await ctx.c.post("/api/functions", json={"name": name, "description": "d", "drive_node_id": nid})


async def test_info_reports_flags_and_limits(ctx, monkeypatch):
    j = (await ctx.c.get("/api/functions/info")).json()
    assert j["enabled"] and j["allowed"] and j["runtimes"] == ["python3.12", "bun"] and j["allow_network"] is False
    assert j["limits"]["timeout_max"] == settings.FUNCTION_TIMEOUT_MAX
    monkeypatch.setattr(settings, "FUNCTION_ALLOWED_EMAILS", "nobody@x.com")
    assert (await ctx.c.get("/api/functions/info")).json()["allowed"] is False  # info 는 막히지 않고 허용 여부만 알려 준다


async def test_feature_off_and_not_allowed(ctx, monkeypatch):
    monkeypatch.setattr(settings, "FUNCTION_ALLOWED_EMAILS", "nobody@x.com")
    r = await ctx.c.get("/api/functions")
    assert r.status_code == 403 and "권한" in r.json()["detail"]
    monkeypatch.setattr(settings, "FUNCTION_ENABLED", False)
    assert (await ctx.c.get("/api/functions")).status_code == 503


async def test_create_from_drive_get_list_and_versions(ctx):
    r = await create(ctx)
    assert r.status_code == 200, r.text
    fn = r.json()
    assert fn["runtime"] == "python3.12" and fn["latest_version"] == 1 and fn["version"]["config"]["handler"] == "main.handler"
    assert fn["version"]["source_ref"]["drive_path"] == "/pkg.zip"
    lst = (await ctx.c.get("/api/functions")).json()["functions"]
    assert [f["name"] for f in lst] == ["hello"] and lst[0]["last_run"]["status"] is None
    d = (await ctx.c.get(f"/api/functions/{fn['id']}")).json()
    assert d["aliases"] == {"latest": 1} and d["secrets"] == [] and len(d["versions"]) == 1
    same = await ctx.c.post(f"/api/functions/{fn['id']}/versions", json={"drive_node_id": await put_zip(ctx, A, "again.zip")})
    assert same.json()["created"] is False  # 같은 내용
    new = await ctx.c.post(f"/api/functions/{fn['id']}/versions", json={"drive_node_id": await put_zip(ctx, A, "v2.zip", good_zip(2))})
    assert new.json()["created"] is True and new.json()["version"]["version"] == 2
    assert (await ctx.c.post("/api/functions", json={"name": "hello", "drive_node_id": await put_zip(ctx, A, "z3.zip")})).status_code == 409


async def test_package_is_copied_so_deleting_the_drive_file_does_not_break_the_function(ctx):
    nid = await put_zip(ctx, A)
    fn = (await ctx.c.post("/api/functions", json={"name": "pinned", "drive_node_id": nid})).json()
    async with ctx.maker() as db:
        await drive_service.trash(db, A.id, [nid]); await drive_service.purge(db, A.id, [nid], store=ctx.store)
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"event": {}, "wait": True})
    assert r.status_code == 200 and r.json()["run"]["status"] == "succeeded"


async def test_create_rejects_bad_drive_nodes_and_packages(ctx):
    r = await ctx.c.post("/api/functions", json={"name": "x", "drive_node_id": "nope"})
    assert r.status_code == 404
    other = await put_zip(ctx, B)  # 남의 Drive 파일
    assert (await ctx.c.post("/api/functions", json={"name": "x", "drive_node_id": other})).status_code == 404
    async with ctx.maker() as db:
        folder = await drive_service.create_folder(db, A.id, "root", "dir")
    assert (await ctx.c.post("/api/functions", json={"name": "x", "drive_node_id": folder.id})).status_code == 400
    bad = await put_zip(ctx, A, "bad.zip", b"not a zip")
    r = await ctx.c.post("/api/functions", json={"name": "x", "drive_node_id": bad})
    assert r.status_code == 400 and "zip" in r.json()["detail"]
    assert (await ctx.c.post("/api/functions", json={"name": "bad name!", "drive_node_id": await put_zip(ctx, A, "ok.zip")})).status_code == 400
    assert (await ctx.c.get("/api/functions")).json()["functions"] == []  # 실패한 등록은 아무것도 남기지 않는다


async def test_alias_and_secret_endpoints_never_return_secret_values(ctx):
    fn = (await create(ctx)).json()
    assert (await ctx.c.put(f"/api/functions/{fn['id']}/aliases/prod", json={"version": 1})).status_code == 200
    assert (await ctx.c.put(f"/api/functions/{fn['id']}/aliases/latest", json={"version": 1})).status_code == 400
    r = await ctx.c.put(f"/api/functions/{fn['id']}/secrets/API_KEY", json={"value": "s3cr3t-value"})
    assert r.json() == {"key": "API_KEY"}
    d = (await ctx.c.get(f"/api/functions/{fn['id']}")).json()
    assert d["secrets"] == ["API_KEY"] and d["aliases"]["prod"] == 1 and "s3cr3t-value" not in json.dumps(d)
    assert (await ctx.c.put(f"/api/functions/{fn['id']}/secrets/FN_X", json={"value": "v"})).status_code == 400
    await ctx.c.delete(f"/api/functions/{fn['id']}/secrets/API_KEY")
    assert (await ctx.c.get(f"/api/functions/{fn['id']}")).json()["secrets"] == []


async def test_invoke_async_then_poll_run_logs_and_list(ctx):
    fn = (await create(ctx)).json()
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"event": {"n": 1}})
    assert r.status_code == 200 and r.json()["done"] is False
    rid = r.json()["run"]["id"]
    assert await ctx.disp.wait_for(rid, 5)
    run = (await ctx.c.get(f"/api/runs/{rid}")).json()
    assert run["status"] == "succeeded" and run["result"] == {"ok": 1} and run["input"] == {"n": 1} and run["version"] == 1
    logs = (await ctx.c.get(f"/api/runs/{rid}/logs")).json()
    assert logs == {"log": "hi\n", "next": 3, "done": True, "truncated": False}
    assert (await ctx.c.get(f"/api/runs/{rid}/logs", params={"after": 3})).json()["log"] == ""  # 증분 조회
    lst = (await ctx.c.get("/api/runs", params={"function_id": fn["id"], "status": "succeeded"})).json()["runs"]
    assert [x["id"] for x in lst] == [rid] and "input" not in lst[0] and "result" not in lst[0]  # 목록은 큰 열을 싣지 않는다
    assert (await ctx.c.get("/api/runs", params={"status": "failed"})).json()["runs"] == []
    assert (await ctx.c.get("/api/functions")).json()["functions"][0]["last_run"]["status"] == "succeeded"


async def test_invoke_wait_returns_result_inline_or_202_on_timeout(ctx, monkeypatch):
    fn = (await create(ctx)).json()
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"event": {}, "wait": True})
    assert r.status_code == 200 and r.json()["done"] and r.json()["run"]["result"] == {"ok": 1}
    ctx.rt.delay = 5
    monkeypatch.setattr(settings, "FUNCTION_SYNC_WAIT_SECONDS", 1)
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"event": {}, "wait": True})
    assert r.status_code == 202 and r.json()["done"] is False and r.json()["run"]["id"]
    ctx.disp.cancel_local(r.json()["run"]["id"])


async def test_invoke_by_alias_idempotency_and_errors(ctx):
    fn = (await create(ctx)).json()
    await ctx.c.post(f"/api/functions/{fn['id']}/versions", json={"drive_node_id": await put_zip(ctx, A, "v2.zip", good_zip(2))})
    await ctx.c.put(f"/api/functions/{fn['id']}/aliases/prod", json={"version": 1})
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"ref": "prod", "idempotency_key": "k"})
    assert r.json()["run"]["version"] == 1
    r2 = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"ref": "prod", "idempotency_key": "k"})
    assert r2.json()["run"]["id"] == r.json()["run"]["id"]
    assert (await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"ref": "nope"})).status_code == 404
    assert (await ctx.c.post("/api/functions/missing/invoke", json={})).status_code == 404


async def test_cancel_endpoint(ctx):
    fn = (await create(ctx)).json()
    ctx.rt.delay = 30
    rid = (await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={})).json()["run"]["id"]
    await asyncio.sleep(0.5)
    r = await ctx.c.post(f"/api/runs/{rid}/cancel")
    assert r.status_code == 200
    assert await ctx.disp.wait_for(rid, 4)
    assert (await ctx.c.get(f"/api/runs/{rid}")).json()["status"] == "cancelled"
    assert (await ctx.c.post(f"/api/runs/{rid}/cancel")).status_code == 409


async def test_other_user_gets_404_everywhere(ctx):
    fn = (await create(ctx)).json()
    rid = (await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={})).json()["run"]["id"]
    CURRENT["user"] = B
    calls = [ctx.c.get(f"/api/functions/{fn['id']}"), ctx.c.put(f"/api/functions/{fn['id']}", json={"description": "x"}), ctx.c.delete(f"/api/functions/{fn['id']}"),
             ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={}), ctx.c.put(f"/api/functions/{fn['id']}/secrets/K", json={"value": "v"}),
             ctx.c.put(f"/api/functions/{fn['id']}/aliases/x", json={"version": 1}), ctx.c.get(f"/api/runs/{rid}"), ctx.c.get(f"/api/runs/{rid}/logs"),
             ctx.c.post(f"/api/runs/{rid}/cancel")]
    for coro in calls:
        assert (await coro).status_code == 404
    assert (await ctx.c.get("/api/functions")).json()["functions"] == [] and (await ctx.c.get("/api/runs")).json()["runs"] == []


async def test_delete_function_endpoint(ctx):
    fn = (await create(ctx)).json()
    assert (await ctx.c.delete(f"/api/functions/{fn['id']}")).json() == {"deleted": True}
    assert (await ctx.c.get(f"/api/functions/{fn['id']}")).status_code == 404
    assert (await create(ctx)).status_code == 200  # 같은 이름을 다시 쓸 수 있다


async def test_admin_switch(ctx):
    fn = (await create(ctx)).json()
    assert (await ctx.c.get("/api/admin/functions")).status_code == 403  # 일반 사용자
    assert (await ctx.c.post(f"/api/admin/functions/{fn['id']}/disable", json={"reason": "x"})).status_code == 403
    CURRENT["user"] = ADMIN
    assert [f["name"] for f in (await ctx.c.get("/api/admin/functions")).json()["functions"]] == ["hello"]
    r = await ctx.c.post(f"/api/admin/functions/{fn['id']}/disable", json={"reason": "남용 신고"})
    assert r.json()["disabled"] is True
    CURRENT["user"] = A
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={})
    assert r.status_code == 403 and "남용 신고" in r.json()["detail"]
    assert (await ctx.c.get(f"/api/functions/{fn['id']}")).json()["disabled"] is True
    CURRENT["user"] = ADMIN
    await ctx.c.post(f"/api/admin/functions/{fn['id']}/enable")
    CURRENT["user"] = A
    assert (await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={})).status_code == 200


async def test_failed_run_is_reported_with_error(ctx):
    fn = (await create(ctx)).json()
    ctx.rt.outcome = RunOutcome(status="failed", error={"type": "ValueError", "message": "boom"}, log="Traceback...\n", exit_code=1, duration_ms=3)
    r = await ctx.c.post(f"/api/functions/{fn['id']}/invoke", json={"wait": True})
    run = r.json()["run"]
    assert r.status_code == 200 and run["status"] == "failed" and run["error"]["type"] == "ValueError" and run["result"] is None and run["exit_code"] == 1


# ── 트리거 API ────────────────────────────────────────────────
async def test_trigger_endpoints_and_webhook_roundtrip(ctx, monkeypatch):
    fn = (await create(ctx)).json()
    sch = await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "schedule", "name": "매일", "schedule_type": "daily", "schedule_time": "09:00"})
    assert sch.status_code == 200 and sch.json()["next_run_at"] and sch.json()["description"].startswith("매일 09:00")
    hook = await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "webhook", "name": "hook"})
    token = hook.json()["token"]
    assert hook.json()["path"] == f"/api/fn-hooks/{token}"
    lst = (await ctx.c.get(f"/api/functions/{fn['id']}/triggers")).json()["triggers"]
    assert {t["kind"] for t in lst} == {"schedule", "webhook"} and token not in json.dumps(lst)  # 목록에는 토큰이 없다
    assert len((await ctx.c.get("/api/fn-triggers")).json()["triggers"]) == 2
    # 웹훅은 로그인 없이 토큰만으로 호출된다
    CURRENT["user"] = None
    app.dependency_overrides.pop(get_current_user, None)
    r = await ctx.c.post(f"/api/fn-hooks/{token}", json={"name": "웹훅"})
    assert r.status_code == 202 and r.json()["status"] == "queued"
    assert await ctx.disp.wait_for(r.json()["run_id"], 5)
    r = await ctx.c.post(f"/api/fn-hooks/{token}", params={"wait": "true"}, json={"n": 1})
    assert r.status_code == 200 and r.json()["status"] == "succeeded" and r.json()["result"] == {"ok": 1}
    r = await ctx.c.post(f"/api/fn-hooks/{token}", content=b"plain text body", headers={"content-type": "text/plain"})  # JSON 이 아니면 문자열로 감싼다
    run_id = r.json()["run_id"]
    assert await ctx.disp.wait_for(run_id, 5)
    async with ctx.maker() as db:
        assert json.loads((await db.get(FunctionRun, run_id)).input) == {"body": "plain text body"}
    assert (await ctx.c.post("/api/fn-hooks/not-a-token", json={})).status_code == 404
    assert (await ctx.c.post(f"/api/fn-hooks/{token}", content=b"x" * (settings.FUNCTION_EVENT_MAX_KB * 1024 + 1))).status_code == 413


async def test_webhook_rate_limit_and_regenerate_via_api(ctx):
    fn = (await create(ctx)).json()
    hook = (await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "webhook"})).json()
    from app.api import functions as fapi

    fapi._hook_limiter.limit = 2
    fapi._hook_limiter._hits.clear()
    codes = [(await ctx.c.post(f"/api/fn-hooks/{hook['token']}", json={})).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
    fapi._hook_limiter.limit = settings.FUNCTION_WEBHOOK_RATE_PER_MIN
    fapi._hook_limiter._hits.clear()
    new = (await ctx.c.post(f"/api/fn-triggers/{hook['id']}/regenerate")).json()["token"]
    assert (await ctx.c.post(f"/api/fn-hooks/{hook['token']}", json={})).status_code == 404 and (await ctx.c.post(f"/api/fn-hooks/{new}", json={})).status_code == 202


async def test_trigger_patch_delete_validation_and_isolation(ctx):
    fn = (await create(ctx)).json()
    bad = await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "schedule", "schedule_type": "daily", "schedule_time": "99:99"})
    assert bad.status_code == 400
    assert (await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "schedule"})).status_code == 400  # schedule_type 없음
    assert (await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "bogus"})).status_code == 422
    t = (await ctx.c.post(f"/api/functions/{fn['id']}/triggers", json={"kind": "schedule", "schedule_type": "interval", "interval_hours": 2})).json()
    assert (await ctx.c.patch(f"/api/fn-triggers/{t['id']}", json={"enabled": False})).json()["enabled"] is False
    CURRENT["user"] = B
    assert (await ctx.c.patch(f"/api/fn-triggers/{t['id']}", json={"enabled": True})).status_code == 404
    assert (await ctx.c.delete(f"/api/fn-triggers/{t['id']}")).status_code == 404
    assert (await ctx.c.get(f"/api/functions/{fn['id']}/triggers")).status_code == 404
    CURRENT["user"] = A
    assert (await ctx.c.delete(f"/api/fn-triggers/{t['id']}")).json() == {"deleted": True}

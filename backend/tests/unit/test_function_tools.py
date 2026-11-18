"""에이전트 Function 도구: sandbox 폴더 → 함수 등록(새 버전), 실행 결과 요약, 권한·오류, tar → zip 변환"""
import asyncio
import io
import json
import tarfile

import pytest

from app.config import settings
from app.services import function_package as fp
from app.services import function_service as fsvc
from app.services.function_runtime import RunOutcome
from app.tools import function_tools as ft
from tests.unit.test_drive_sandbox import FakeManager
from tests.unit.test_function_service import U1, env, make  # noqa: F401  (fixtures)

PKG = {"function.json": json.dumps({"runtime": "python3.12", "handler": "main.handler"}).encode(), "main.py": b"def handler(e, c):\n    return 1\n"}


@pytest.fixture
def tool_env(env, monkeypatch):
    mgr = FakeManager({"/workspace/fn": dict(PKG)})

    async def container(*a, **k):
        return "c1"

    monkeypatch.setattr(ft, "_container", container)
    monkeypatch.setattr(ft, "_manager", lambda: mgr)
    monkeypatch.setattr(ft, "get_dispatcher", lambda: env.disp)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", env.maker)
    from app.services import drive_storage

    monkeypatch.setattr(drive_storage, "storage", env.store)  # 도구는 전역 저장소를 쓴다
    env.mgr = mgr
    return env


def tools(user=U1):
    kw = dict(user_id=user.id, sandbox_cid="")
    return ft.RegisterFunctionTool(**kw), ft.InvokeFunctionTool(**kw), ft.ListFunctionsTool(**kw)


async def test_register_creates_function_then_versions_then_detects_identical(tool_env):
    reg, _, _ = tools()
    out = await reg._arun(path="fn", name="my-fn", description="d")
    assert "registered" in out and "python3.12" in out and "v1" in out
    fns = await fsvc.list_functions(tool_env.db, U1.id)
    assert [f.name for f in fns] == ["my-fn"]
    ver = (await fsvc.list_versions(tool_env.db, fns[0]))[0]
    assert ver.source == "agent" and ver.source_ref == {"workspace_path": "/workspace/fn"}
    assert "identical" in await reg._arun(path="fn", name="my-fn")  # 같은 내용은 새 버전이 아니다
    tool_env.mgr.tree["/workspace/fn"]["main.py"] = b"def handler(e, c):\n    return 2\n"
    assert "new version v2" in await reg._arun(path="fn", name="my-fn")


async def test_register_errors_are_returned_as_text_not_raised(tool_env):
    reg, _, _ = tools()
    assert reg.name == "register_function"
    assert (await reg._arun(path="/workspace", name="x")).startswith("Error:")  # 작업공간 전체
    assert "작업공간" in await reg._arun(path="../etc", name="x")
    tool_env.mgr.tree["/workspace/nojson"] = {"main.py": b"x"}
    assert "function.json" in await reg._arun(path="nojson", name="x")
    assert (await reg._arun(path="missing", name="x")).startswith("Error:")
    assert "이름" in await reg._arun(path="fn", name="bad name!")
    assert await fsvc.list_functions(tool_env.db, U1.id) == []  # 실패한 등록은 아무것도 남기지 않는다


async def test_tools_respect_the_users_permission(tool_env, monkeypatch):
    monkeypatch.setattr(settings, "FUNCTION_ALLOWED_EMAILS", "someone-else@x.com")
    reg, inv, lst = tools()
    for t, kw in ((reg, dict(path="fn", name="x")), (inv, dict(name="x")), (lst, {})):
        assert "권한" in await t._arun(**kw)


async def test_invoke_returns_status_result_and_log_tail(tool_env):
    await make(tool_env, name="calc")
    loop = asyncio.create_task(tool_env.disp.run_forever())
    try:
        _, inv, _ = tools()
        tool_env.rt.outcome = RunOutcome(status="succeeded", result={"sum": 5}, log="line1\nline2\n", duration_ms=12, cold_start_ms=3)
        out = await inv._arun(name="calc", event={"a": 2, "b": 3})
        head, _, tail = out.partition("\n--- log tail ---\n")
        data = json.loads(head)
        assert data["status"] == "succeeded" and data["result"] == {"sum": 5} and data["version"] == 1 and "line2" in tail
        assert json.loads(tool_env.rt.calls[0].event) == {"a": 2, "b": 3}
        run = (await fsvc.list_runs(tool_env.db, U1.id))[0]
        assert run.trigger == "agent"  # 에이전트가 시작한 실행으로 기록된다
        tool_env.rt.outcome = RunOutcome(status="failed", error={"type": "ValueError", "message": "boom"}, log="Traceback...\n", exit_code=1)
        out = await inv._arun(name="calc")
        assert json.loads(out.split("\n---")[0])["error"]["type"] == "ValueError" and "Traceback" in out
    finally:
        loop.cancel()
        for t in list(tool_env.disp._tasks):
            t.cancel()
        await asyncio.gather(loop, *tool_env.disp._tasks, return_exceptions=True)


async def test_invoke_unknown_function_and_still_running(tool_env, monkeypatch):
    _, inv, _ = tools()
    assert "함수를 찾을 수 없습니다" in await inv._arun(name="nope")
    await make(tool_env, name="slow")
    monkeypatch.setattr(settings, "FUNCTION_SYNC_WAIT_SECONDS", 0)  # 기다리지 않고 바로 run id 를 돌려준다 (디스패처는 돌지 않는다)
    out = await inv._arun(name="slow")
    assert "still queued" in out and "Workflow" in out


async def test_list_functions_output(tool_env):
    _, _, lst = tools()
    assert "No functions" in await lst._arun()
    await make(tool_env, name="alpha")
    out = await lst._arun()
    assert "alpha" in out and "python3.12" in out and "v1" in out and "last run: none" in out


# ── tar → zip ─────────────────────────────────────────────────
def make_tar(tmp_path, entries):
    p = tmp_path / "x.tar"
    with tarfile.open(p, "w") as t:
        for name, val in entries.items():
            if val is None:
                ti = tarfile.TarInfo(name); ti.type = tarfile.DIRTYPE; t.addfile(ti)
            elif isinstance(val, tuple) and val[0] == "link":
                ti = tarfile.TarInfo(name); ti.type = tarfile.SYMTYPE; ti.linkname = val[1]; t.addfile(ti)
            else:
                data, mode = val if isinstance(val, tuple) else (val, 0o644)
                ti = tarfile.TarInfo(name); ti.size, ti.mode = len(data), mode; t.addfile(ti, io.BytesIO(data))
    return str(p)


def test_zip_from_tar_strips_top_dir_skips_links_and_keeps_exec_bit(tmp_path):
    path = make_tar(tmp_path, {"proj": None, "proj/function.json": b"{}", "proj/main.py": b"x", "proj/bin": None, "proj/bin/run.sh": (b"#!/bin/sh", 0o755),
                               "proj/link": ("link", "/etc/passwd"), "__MACOSX/proj/._main.py": b"junk"})
    data, skipped = fp.zip_from_tar(path, 10 * 1024 * 1024)
    import zipfile

    z = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(z.namelist()) == ["bin/run.sh", "function.json", "main.py"] and skipped == 1
    assert (z.getinfo("bin/run.sh").external_attr >> 16) & 0o111 and not (z.getinfo("main.py").external_attr >> 16) & 0o111


def test_zip_from_tar_enforces_size_and_roundtrips_through_inspect(tmp_path):
    big = make_tar(tmp_path, {"p": None, "p/a.bin": b"x" * 5000})
    with pytest.raises(fp.PackageError, match="너무 큽니다"):
        fp.zip_from_tar(big, 1000)
    ok = make_tar(tmp_path, {"p": None, "p/function.json": json.dumps({"runtime": "python3.12", "handler": "main.handler"}).encode(), "p/main.py": b"def handler(e, c): return 1"})
    data, _ = fp.zip_from_tar(ok, 10**6)
    assert fp.inspect_zip(data).config["handler"] == "main.handler"  # 만든 zip 은 그대로 패키지 검증을 통과한다

"""Drive API: 업로드(스트리밍 한도)·다운로드 헤더·소유자 격리·휴지통·sandbox 저장/첨부 (메모리 DB + 메모리 저장소 + 가짜 sandbox)"""
import hashlib
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
from app.services import drive_storage
from tests.unit.test_drive_sandbox import FakeManager
from tests.unit.test_drive_service import A, B, MemStore

CURRENT = {"id": A}


@pytest_asyncio.fixture
async def client(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[DriveNode.__table__, DriveUsage.__table__]))
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def session_dep():
        async with maker() as s:
            yield s

    store = MemStore()
    monkeypatch.setattr(drive_storage, "storage", store)
    monkeypatch.setattr(drive_storage, "enabled", lambda: True)
    CURRENT["id"] = A
    app.dependency_overrides[get_session] = session_dep
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=CURRENT["id"])
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        c.store = store  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def upload(c, name, data, parent="root"):
    return await c.post("/api/drive/files", params={"name": name, "parent_id": parent}, content=data)


async def test_upload_list_download_roundtrip_and_headers(client):
    data = b"\x00\x01binary" * 1000
    r = await upload(client, "보고서 data.bin", data)
    assert r.status_code == 200 and r.json()["size_bytes"] == len(data) and r.json()["name"] == "보고서 data.bin"
    node = r.json()
    listing = (await client.get("/api/drive/nodes")).json()
    assert listing["path"] == "/" and [n["name"] for n in listing["nodes"]] == ["보고서 data.bin"]
    dl = await client.get(f"/api/drive/files/{node['id']}/download")
    assert dl.content == data and hashlib.sha256(dl.content).hexdigest() == hashlib.sha256(data).hexdigest()
    h = dl.headers
    assert "attachment" in h["content-disposition"] and "%EB%B3%B4%EA%B3%A0%EC%84%9C" in h["content-disposition"]
    assert h["x-content-type-options"] == "nosniff" and "no-store" in h["cache-control"]
    assert h["content-type"].startswith("application/octet-stream")  # 어떤 형식도 브라우저가 열지 않는다


async def test_html_and_svg_are_always_downloads_never_inline(client):
    for name in ("x.html", "x.svg"):
        n = (await upload(client, name, b"<script>alert(1)</script>")).json()
        h = (await client.get(f"/api/drive/files/{n['id']}/download")).headers
        assert h["content-disposition"].startswith("attachment") and h["content-type"].startswith("application/octet-stream")


async def test_upload_limit_enforced_while_streaming(client, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_MAX_FILE_MB", 1)
    assert (await upload(client, "big.bin", b"x" * (2 * 1024 * 1024))).status_code == 413  # Content-Length 사전 검사

    async def chunks():  # 길이 헤더 없이 청크 전송
        for _ in range(40):
            yield b"y" * 65536

    r = await client.post("/api/drive/files", params={"name": "big2.bin", "parent_id": "root"}, content=chunks())
    assert r.status_code == 413
    assert client.store.objects == {} and (await client.get("/api/drive/usage")).json()["used_bytes"] == 0


async def test_error_mapping_and_validation(client):
    assert (await client.post("/api/drive/folders", json={"parent_id": "root", "name": "a/b"})).status_code == 400
    assert (await client.post("/api/drive/folders", json={"parent_id": "root", "name": "Docs"})).status_code == 200
    r = await client.post("/api/drive/folders", json={"parent_id": "root", "name": "docs"})
    assert r.status_code == 409 and "detail" in r.json()
    assert (await client.patch("/api/drive/nodes/nope", json={"name": "x"})).status_code == 404
    assert (await client.patch("/api/drive/nodes/root", json={})).status_code == 400
    assert (await client.post("/api/drive/nodes/move", json={"ids": [], "parent_id": "root"})).status_code == 422  # 빈 목록


async def test_disabled_drive_returns_503(client, monkeypatch):
    monkeypatch.setattr(drive_storage, "enabled", lambda: False)
    assert (await client.get("/api/drive/nodes")).status_code == 503


async def test_other_user_cannot_access(client):
    folder = (await client.post("/api/drive/folders", json={"parent_id": "root", "name": "mine"})).json()
    f = (await upload(client, "secret.txt", b"s", folder["id"])).json()
    CURRENT["id"] = B
    for resp in [
        await client.get("/api/drive/nodes", params={"parent_id": folder["id"]}),
        await client.get(f"/api/drive/files/{f['id']}/download"),
        await client.patch(f"/api/drive/nodes/{f['id']}", json={"name": "x"}),
        await upload(client, "x.txt", b"x", folder["id"]),
        await client.post("/api/drive/folders", json={"parent_id": folder["id"], "name": "x"}),
        await client.post("/api/drive/files/%s/attach" % f["id"], json={}),
    ]:
        assert resp.status_code == 404, resp.text
    assert (await client.post("/api/drive/nodes/delete", json={"ids": [f["id"]]})).json() == {"trashed": 0}
    CURRENT["id"] = A
    assert (await client.get(f"/api/drive/files/{f['id']}/download")).status_code == 200


async def test_trash_restore_purge_via_api(client):
    f = (await upload(client, "a.txt", b"abc")).json()
    assert (await client.post("/api/drive/nodes/delete", json={"ids": [f["id"]]})).json() == {"trashed": 1}
    assert (await client.get(f"/api/drive/files/{f['id']}/download")).status_code == 404
    trash = (await client.get("/api/drive/trash")).json()
    assert [n["id"] for n in trash["nodes"]] == [f["id"]] and trash["retention_days"] == settings.DRIVE_TRASH_RETENTION_DAYS
    assert (await client.post("/api/drive/trash/restore", json={"ids": [f["id"]]})).status_code == 200
    assert (await client.get(f"/api/drive/files/{f['id']}/download")).content == b"abc"
    await client.post("/api/drive/nodes/delete", json={"ids": [f["id"]]})
    assert (await client.post("/api/drive/trash/purge", json={"ids": [f["id"]]})).json() == {"purged": 1}
    assert client.store.objects == {} and (await client.get("/api/drive/usage")).json()["used_bytes"] == 0
    assert (await client.post("/api/drive/trash/empty")).json() == {"purged": 0}


async def test_rename_move_resolve(client):
    a = (await client.post("/api/drive/folders", json={"parent_id": "root", "name": "a"})).json()
    f = (await upload(client, "x.txt", b"1")).json()
    assert (await client.patch(f"/api/drive/nodes/{f['id']}", json={"name": "y.txt", "parent_id": a["id"]})).json()["name"] == "y.txt"
    r = (await client.get("/api/drive/resolve", params={"path": "/A/Y.TXT"})).json()
    assert r["path"] == "/a/y.txt" and r["id"] == f["id"]
    assert (await client.get("/api/drive/resolve", params={"path": "/nope"})).status_code == 404


async def test_pagination_cursor(client):
    for i in range(5):
        await client.post("/api/drive/folders", json={"parent_id": "root", "name": f"f{i}"})
    p1 = (await client.get("/api/drive/nodes", params={"limit": 2})).json()
    p2 = (await client.get("/api/drive/nodes", params={"limit": 2, "cursor": p1["next_cursor"]})).json()
    p3 = (await client.get("/api/drive/nodes", params={"limit": 2, "cursor": p2["next_cursor"]})).json()
    assert [n["name"] for n in p1["nodes"] + p2["nodes"] + p3["nodes"]] == [f"f{i}" for i in range(5)] and p3["next_cursor"] is None


@pytest.fixture
def fake_sandbox(monkeypatch):
    from app.services import sandbox_service as ss

    mgr = FakeManager({"/workspace/out/report.pdf": b"%PDF", "/workspace/proj": {"a.py": b"1", "node_modules": {"x": b"z"}}})

    async def exec_command(cid, cmd, timeout=30):
        return 0, "doc.txt\n", ""  # uploads 폴더에 doc.txt 가 이미 있다

    mgr.exec_command = exec_command  # type: ignore[attr-defined]
    sb = SimpleNamespace(status="running", container_id="c1")

    async def get_sb(*a, **k):
        return sb

    async def scope(*a, **k):
        return None

    monkeypatch.setattr(ss, "sandbox_manager", mgr)
    monkeypatch.setattr(ss.SandboxService, "get_sandbox", staticmethod(get_sb))
    monkeypatch.setattr(ss.SandboxService, "get_or_create_sandbox", staticmethod(get_sb))
    monkeypatch.setattr(ss, "resolve_scope", scope)
    return mgr


async def test_import_from_sandbox(client, fake_sandbox):
    r = await client.post("/api/drive/import/sandbox", json={"paths": ["out/report.pdf", "proj"], "parent_id": "root"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [n["name"] for n in body["saved"]] == ["report.pdf", "proj"] and body["files"] == 2  # node_modules 제외
    assert all(n["source"] == "sandbox" for n in body["saved"])
    assert (await client.get("/api/drive/resolve", params={"path": "/proj/a.py"})).status_code == 200


async def test_import_rejects_workspace_root_escape_and_missing(client, fake_sandbox):
    for p in ("/workspace", "../etc/passwd", "/etc/passwd"):
        assert (await client.post("/api/drive/import/sandbox", json={"paths": [p]})).status_code == 400, p
    assert (await client.post("/api/drive/import/sandbox", json={"paths": ["nope.txt"]})).status_code == 404


async def test_attach_copies_into_uploads_with_unique_name(client, fake_sandbox):
    f = (await upload(client, "doc.txt", b"hello")).json()  # uploads 에 doc.txt 가 이미 있다고 가정(fake)
    r = await client.post(f"/api/drive/files/{f['id']}/attach", json={})
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "doc (1).txt", "path": "/workspace/uploads/doc (1).txt", "size": 5}
    assert fake_sandbox.written["/workspace/uploads/doc (1).txt"] == b"hello"


async def test_attach_rejects_folder_and_oversize(client, fake_sandbox, monkeypatch):
    d = (await client.post("/api/drive/folders", json={"parent_id": "root", "name": "d"})).json()
    assert (await client.post(f"/api/drive/files/{d['id']}/attach", json={})).status_code == 400
    f = (await upload(client, "big.bin", b"x" * 100)).json()
    monkeypatch.setattr(settings, "UPLOAD_MAX_MB", 0)
    assert (await client.post(f"/api/drive/files/{f['id']}/attach", json={})).status_code == 413

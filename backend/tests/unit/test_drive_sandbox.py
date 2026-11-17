"""sandbox ↔ Drive 전송: 파일·폴더 저장, 제외 디렉터리, 한도, 불러오기 (가짜 sandbox 매니저 + 메모리 DB/저장소)"""
import io
import tarfile

import pytest

from app.config import settings
from app.services import drive_sandbox as sb
from app.services import drive_service as svc
from app.services.drive_service import DriveError
from tests.unit.test_drive_service import A, MemStore, db, store  # noqa: F401  (fixtures)


class FakeManager:
    """docker 대신 {경로: bytes 또는 dict(폴더)} 로 get_archive 와 같은 tar 를 만든다."""

    def __init__(self, tree: dict):
        self.tree, self.written = tree, {}

    async def export_path(self, container_id, path, out_path, max_bytes):
        base = path.rsplit("/", 1)[-1]
        node = self.tree.get(path)
        if node is None:
            raise FileNotFoundError(path)
        with tarfile.open(out_path, "w") as t:
            def add(name, obj):
                if isinstance(obj, dict):
                    ti = tarfile.TarInfo(name); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; t.addfile(ti)
                    for k, v in obj.items():
                        add(f"{name}/{k}", v)
                else:
                    ti = tarfile.TarInfo(name); ti.size = len(obj); t.addfile(ti, io.BytesIO(obj))
            add(base, node)
        import os
        if os.path.getsize(out_path) > max_bytes:
            raise RuntimeError("too big")

    async def write_file(self, container_id, path, data, mode=0o644):
        self.written[path] = data


async def test_save_single_file(db, store):
    m = FakeManager({"/workspace/out/report.pdf": b"%PDF-1"})
    r = await sb.save_from_sandbox(db, A, m, "c1", "/workspace/out/report.pdf", "root", source="agent", source_ref={"conversation_id": "x"}, store=store)
    assert r["node"].name == "report.pdf" and r["files"] == 1
    assert store.objects[r["node"].storage_key] == b"%PDF-1"
    assert r["node"].source == "agent"


async def test_save_with_new_name_and_numbering(db, store):
    m = FakeManager({"/workspace/a.txt": b"1"})
    r1 = await sb.save_from_sandbox(db, A, m, "c", "/workspace/a.txt", "root", name="결과.txt", store=store)
    r2 = await sb.save_from_sandbox(db, A, m, "c", "/workspace/a.txt", "root", name="결과.txt", store=store)
    assert (r1["node"].name, r2["node"].name) == ("결과.txt", "결과 (1).txt")


async def test_save_folder_keeps_structure_and_skips_junk(db, store):
    tree = {"/workspace/proj": {"README.md": b"hi", "src": {"main.py": b"print(1)", "__pycache__": {"x.pyc": b"z"}},
                                 "node_modules": {"lib": {"i.js": b"j"}}, ".git": {"HEAD": b"h"}}}
    m = FakeManager(tree)
    r = await sb.save_from_sandbox(db, A, m, "c", "/workspace/proj", "root", store=store)
    assert r["files"] == 2  # README.md, src/main.py 만
    assert (await svc.resolve(db, A, "/proj/README.md")) and (await svc.resolve(db, A, "/proj/src/main.py"))
    for junk in ("/proj/node_modules", "/proj/.git", "/proj/src/__pycache__"):
        assert await svc.resolve(db, A, junk) is None
    # 같은 폴더를 다시 저장하면 합치지 않고 새 폴더로
    r2 = await sb.save_from_sandbox(db, A, m, "c", "/workspace/proj", "root", store=store)
    assert r2["node"].name == "proj (1)"
    assert await svc.resolve(db, A, "/proj (1)/src/main.py")


async def test_save_missing_path_and_empty_folder(db, store):
    with pytest.raises(DriveError) as e:
        await sb.save_from_sandbox(db, A, FakeManager({}), "c", "/workspace/nope", "root", store=store)
    assert e.value.status == 404
    with pytest.raises(DriveError) as e:
        await sb.save_from_sandbox(db, A, FakeManager({"/workspace/empty": {}}), "c", "/workspace/empty", "root", store=store)
    assert e.value.status == 400


async def test_save_limits_checked_before_writing_anything(db, store, monkeypatch):
    monkeypatch.setattr(settings, "DRIVE_IMPORT_MAX_FILES", 2)
    m = FakeManager({"/workspace/many": {f"f{i}.txt": b"x" for i in range(5)}})
    with pytest.raises(DriveError) as e:
        await sb.save_from_sandbox(db, A, m, "c", "/workspace/many", "root", store=store)
    assert e.value.status == 413
    assert store.objects == {} and await svc.resolve(db, A, "/many") is None  # 아무것도 쓰지 않았다


async def test_save_into_other_users_folder_denied(db, store):
    from tests.unit.test_drive_service import B

    theirs = await svc.create_folder(db, B, "root", "theirs")
    with pytest.raises(DriveError) as e:
        await sb.save_from_sandbox(db, A, FakeManager({"/workspace/a.txt": b"1"}), "c", "/workspace/a.txt", theirs.id, store=store)
    assert e.value.status == 404


async def test_ensure_folder_path_reuses_and_creates(db):
    f1 = await svc.ensure_folder_path(db, A, "/Agent Outputs/2026-11")
    f2 = await svc.ensure_folder_path(db, A, "/agent outputs/2026-11/")  # 대소문자 무시, 끝 슬래시
    assert f1.id == f2.id and await svc.node_path(db, f1) == "/Agent Outputs/2026-11"
    assert (await svc.ensure_folder_path(db, A, "/")).id == A


async def test_ensure_folder_path_rejects_file_in_the_way(db, store):
    import hashlib
    await svc.create_file(db, A, "root", "docs", io.BytesIO(b"x"), 1, hashlib.sha256(b"x").hexdigest(), store=store)
    with pytest.raises(DriveError) as e:
        await svc.ensure_folder_path(db, A, "/docs/sub")
    assert e.value.status == 409


async def test_load_to_sandbox(db, store):
    m = FakeManager({"/workspace/a.csv": b"a,b\n1,2\n"})
    await sb.save_from_sandbox(db, A, m, "c", "/workspace/a.csv", "root", store=store)
    out = await sb.load_to_sandbox(db, A, m, "c", "/a.csv", "/workspace/inputs/", store=store)
    assert out["path"] == "/workspace/inputs/a.csv" and m.written["/workspace/inputs/a.csv"] == b"a,b\n1,2\n"
    out = await sb.load_to_sandbox(db, A, m, "c", "/A.CSV", "/workspace/renamed.csv", store=store)  # 대소문자 무시, 파일명 지정
    assert m.written["/workspace/renamed.csv"] == b"a,b\n1,2\n"


async def test_load_rejects_folder_missing_and_too_large(db, store, monkeypatch):
    m = FakeManager({"/workspace/a.csv": b"x" * 100})
    await sb.save_from_sandbox(db, A, m, "c", "/workspace/a.csv", "root", store=store)
    await svc.create_folder(db, A, "root", "dir")
    with pytest.raises(DriveError) as e:
        await sb.load_to_sandbox(db, A, m, "c", "/dir", "/workspace/", store=store)
    assert e.value.status == 400
    with pytest.raises(DriveError) as e:
        await sb.load_to_sandbox(db, A, m, "c", "/nope", "/workspace/", store=store)
    assert e.value.status == 404
    monkeypatch.setattr(settings, "DRIVE_LOAD_MAX_MB", 0)
    with pytest.raises(DriveError) as e:
        await sb.load_to_sandbox(db, A, m, "c", "/a.csv", "/workspace/", store=store)
    assert e.value.status == 413

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import sandbox_service as sbs_mod
from app.services import skill_service as sk_mod
from app.services.skill_service import SkillService
from app.tools.skill_tool import LoadSkillTool


class FakeManager:
    """sandbox 컨테이너 대신 skill 디렉터리 이름 집합을 들고 있는 가짜."""

    def __init__(self, present=()):
        self.present = set(present)
        self.put = []
        self.running = True

    async def exec_command(self, container_id, command, timeout=30):
        return 0, "\n".join(sorted(self.present)) + "\n", ""

    async def put_directory(self, container_id, local_dir, dest_parent, name):
        self.put.append((name, dest_parent))
        self.present.add(name)
        return f"{dest_parent}/{name}"

    async def is_running(self, container_id):
        return self.running


@pytest.fixture
def skill_dirs(tmp_path):
    out = {}
    for n in ("pptx", "pdf"):
        d = tmp_path / n
        d.mkdir()
        (d / "SKILL.md").write_text(f"---\nname: {n}\n---\n{n} 지침", encoding="utf-8")
        out[n] = d
    return out


def skills(dirs, *names):
    return [SimpleNamespace(name=n, install_path=str(dirs[n])) for n in names]


def run(coro):
    return asyncio.run(coro)


def test_ensure_in_sandbox_copies_only_missing_skills(monkeypatch, skill_dirs):
    fake = FakeManager(present={"pdf"})  # pdf 는 이미 있다 (sandbox 안에서 수정됐을 수 있으므로 덮어쓰면 안 된다)
    monkeypatch.setattr(sk_mod, "sandbox_manager", fake)
    copied = run(SkillService.ensure_in_sandbox("c1", skills(skill_dirs, "pptx", "pdf")))
    assert copied == ["pptx"] and fake.put == [("pptx", "/workspace/skills")]
    assert run(SkillService.ensure_in_sandbox("c1", skills(skill_dirs, "pptx", "pdf"))) == []  # 두 번째는 할 일이 없다
    assert run(SkillService.ensure_in_sandbox("c1", [])) == []


def test_ensure_in_sandbox_skips_skills_whose_host_copy_is_gone(monkeypatch, tmp_path):
    fake = FakeManager()
    monkeypatch.setattr(sk_mod, "sandbox_manager", fake)
    ghost = [SimpleNamespace(name="ghost", install_path=str(tmp_path / "missing"))]
    assert run(SkillService.ensure_in_sandbox("c1", ghost)) == [] and fake.put == []


# ── load_skill ────────────────────────────────────────────────────────────────
class _Session:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


def patch_tool_env(monkeypatch, skill_dirs, manager, sandbox):
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr(sbs_mod, "sandbox_manager", manager)
    monkeypatch.setattr(sk_mod, "sandbox_manager", manager)

    async def get_sandbox(user_id, db):
        return sandbox

    async def list_skills(user_id, db):
        return skills(skill_dirs, "pptx", "pdf")

    monkeypatch.setattr(sbs_mod.SandboxService, "get_sandbox", staticmethod(get_sandbox))
    monkeypatch.setattr(SkillService, "list_skills", staticmethod(list_skills))


def tool(skill_dirs):
    return LoadSkillTool(skills={n: str(d) for n, d in skill_dirs.items()}, user_id="u1")


def test_load_skill_copies_missing_skill_into_running_sandbox(monkeypatch, skill_dirs):
    mgr = FakeManager()
    patch_tool_env(monkeypatch, skill_dirs, mgr, SimpleNamespace(status="running", container_id="c1"))
    out = run(tool(skill_dirs)._arun("pptx"))
    assert "pptx 지침" in out and "방금 `/workspace/skills/pptx/` 로 복사" in out
    assert mgr.put == [("pptx", "/workspace/skills")]


def test_load_skill_reports_when_already_in_sandbox(monkeypatch, skill_dirs):
    mgr = FakeManager(present={"pptx"})
    patch_tool_env(monkeypatch, skill_dirs, mgr, SimpleNamespace(status="running", container_id="c1"))
    out = run(tool(skill_dirs)._arun("pptx"))
    assert "`/workspace/skills/pptx/` 에 있습니다" in out and mgr.put == []


def test_load_skill_without_running_sandbox_says_so_and_does_not_create_one(monkeypatch, skill_dirs):
    mgr = FakeManager()
    patch_tool_env(monkeypatch, skill_dirs, mgr, None)
    out = run(tool(skill_dirs)._arun("pptx"))
    assert "실행 중인 sandbox 가 없습니다" in out and mgr.put == []
    mgr.running = False
    patch_tool_env(monkeypatch, skill_dirs, mgr, SimpleNamespace(status="running", container_id="c1"))
    assert "실행 중인 sandbox 가 없습니다" in run(tool(skill_dirs)._arun("pptx"))


def test_load_skill_sandbox_failure_does_not_break_reading(monkeypatch, skill_dirs):
    mgr = FakeManager()

    async def boom(*a, **k):
        raise RuntimeError("docker down")

    mgr.exec_command = boom
    patch_tool_env(monkeypatch, skill_dirs, mgr, SimpleNamespace(status="running", container_id="c1"))
    out = run(tool(skill_dirs)._arun("pptx"))
    assert "pptx 지침" in out and "확인하지 못했습니다" in out and "docker down" in out


def test_load_skill_errors_and_non_skill_md_files_get_no_sandbox_note(monkeypatch, skill_dirs):
    patch_tool_env(monkeypatch, skill_dirs, FakeManager(), SimpleNamespace(status="running", container_id="c1"))
    t = tool(skill_dirs)
    assert run(t._arun("nope")).startswith("Skill 'nope' not found") and "[Sandbox]" not in run(t._arun("nope"))
    (skill_dirs["pptx"] / "extra.md").write_text("x", encoding="utf-8")
    assert "[Sandbox]" not in run(t._arun("pptx", "extra.md"))
    assert t._run("pptx").startswith("---")  # 동기 경로는 호스트 읽기만 한다


def test_get_or_create_sandbox_source_wires_skill_sync():
    """새 컨테이너를 만든 직후 skill 을 채우는 호출이 get_or_create_sandbox 안에 있어야 한다 (회귀 방지)."""
    src = Path(sbs_mod.__file__).read_text(encoding="utf-8")
    body = src[src.index("async def get_or_create_sandbox"): src.index("async def get_sandbox")]
    assert "ensure_in_sandbox" in body and body.index("sandbox_backup.restore") < body.index("ensure_in_sandbox")

import asyncio
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import sandbox_service as mod
from app.services.sandbox_service import SandboxService


class _Session:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *a):
        return False


class FakeBackup:
    def __init__(self, enabled=True, has=True):
        self.enabled, self.has, self.checked = enabled, has, []

    async def exists(self, session_id):
        self.checked.append(session_id)
        return self.has


class FakeManager:
    def __init__(self, running=False):
        self.running = running

    async def is_running(self, cid):
        return self.running


@pytest.fixture
def env(monkeypatch):
    calls = {"created": 0}
    state = SimpleNamespace(sb=SimpleNamespace(id="sess-1", status="stopped", container_id=None))

    async def latest(user_id, db):
        return state.sb

    async def get_or_create(user_id, db):
        calls["created"] += 1
        return SimpleNamespace(id="sess-1", restored=True)

    monkeypatch.setattr("app.db.session.AsyncSessionLocal", lambda: _Session())
    monkeypatch.setattr(SandboxService, "_latest", staticmethod(latest))
    monkeypatch.setattr(SandboxService, "get_or_create_sandbox", staticmethod(get_or_create))
    monkeypatch.setattr(mod, "sandbox_manager", FakeManager())
    monkeypatch.setattr(mod, "sandbox_backup", FakeBackup())
    return SimpleNamespace(calls=calls, state=state)


def run():
    return asyncio.run(SandboxService.restore_if_backed_up("u1"))


def test_restores_when_stopped_and_backup_exists(env):
    assert run() is True and env.calls["created"] == 1
    assert mod.sandbox_backup.checked == ["sess-1"]  # 세션 id(Sandbox.id)로 백업을 찾는다


def test_does_nothing_without_backup_so_chats_that_dont_need_a_sandbox_stay_cheap(env, monkeypatch):
    monkeypatch.setattr(mod, "sandbox_backup", FakeBackup(has=False))
    assert run() is False and env.calls["created"] == 0


def test_does_nothing_when_backup_disabled_or_no_session_or_already_running(env, monkeypatch):
    monkeypatch.setattr(mod, "sandbox_backup", FakeBackup(enabled=False))
    assert run() is False
    monkeypatch.setattr(mod, "sandbox_backup", FakeBackup())
    env.state.sb = None
    assert run() is False
    env.state.sb = SimpleNamespace(id="s", status="running", container_id="c1")
    monkeypatch.setattr(mod, "sandbox_manager", FakeManager(running=True))
    assert run() is False and env.calls["created"] == 0
    # DB 는 running 인데 컨테이너가 사라진 경우(Docker 재시작)는 복구 대상이다
    monkeypatch.setattr(mod, "sandbox_manager", FakeManager(running=False))
    assert run() is True


def test_idle_timeout_defaults_to_five_minutes():
    assert settings.SANDBOX_IDLE_MINUTES == 5


def test_reap_idle_is_off_without_backup(monkeypatch):
    monkeypatch.setattr(mod, "sandbox_backup", FakeBackup(enabled=False))
    assert asyncio.run(SandboxService.reap_idle()) == 0  # 백업 불가면 자동 종료하지 않는다 (데이터 유실 방지)

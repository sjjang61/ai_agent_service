"""대화 공유: 스냅샷에 들어가는 것/안 들어가는 것, 토큰 검증, 만료"""
import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.config import settings
from app.services import share_service as ss


def _msg(role, content, steps=None, at=None):
    return SimpleNamespace(role=role, content=content, agent_steps=steps or [], created_at=at or datetime(2026, 1, 1))


WIDGET = {"type": "table", "title": "표", "spec": {"columns": ["a"], "rows": [[1]]}}


def test_snapshot_keeps_only_text_and_widgets():
    steps = [
        {"type": "tool_call", "tool": "exec_command", "input": {"cmd": "cat ~/.ssh/id_rsa"}},
        {"type": "tool_result", "tool": "exec_command", "output": "SECRET=abc"},
        {"type": "tool_result", "tool": "create_widget", "output": json.dumps({"ok": True, "widget": WIDGET})},
    ]
    snap = ss.build_snapshot([_msg("user", "안녕"), _msg("assistant", "답변", steps), _msg("system", "내부 지시")])
    assert [m["role"] for m in snap] == ["user", "assistant"]
    assert snap[1]["widgets"] == [WIDGET] and snap[0]["widgets"] == []
    dumped = json.dumps(snap, ensure_ascii=False)
    assert "SECRET" not in dumped and "id_rsa" not in dumped and "내부 지시" not in dumped
    assert set(snap[1]) == {"role", "content", "widgets", "created_at"}  # agent_steps/첨부/참조는 필드 자체가 없다


def test_empty_messages_skipped_and_limit_keeps_latest():
    snap = ss.build_snapshot([_msg("user", "  "), _msg("user", "a"), _msg("assistant", "b"), _msg("user", "c")], limit=2)
    assert [m["content"] for m in snap] == ["b", "c"]


def test_broken_widget_output_ignored():
    steps = [{"type": "tool_result", "tool": "create_widget", "output": "오류: 실패"}, {"type": "tool_result", "tool": "create_widget", "output": json.dumps({"ok": False})}]
    assert ss.extract_widgets(steps) == []


def test_bad_token_never_touches_db():
    class Boom:
        async def execute(self, *a, **k):
            raise AssertionError("DB 를 읽으면 안 된다")

    for t in ["", "short", "../etc/passwd", "a" * 80, "has space has space has space"]:
        assert asyncio.run(ss.ShareService.public(t, Boom())) is None


def test_expiry_follows_setting(monkeypatch):
    monkeypatch.setattr(settings, "SHARE_EXPIRE_DAYS", 0)
    assert ss._expiry() is None
    monkeypatch.setattr(settings, "SHARE_EXPIRE_DAYS", 7)
    d = ss._expiry()
    assert timedelta(days=6, hours=23) < d - ss._now() <= timedelta(days=7)

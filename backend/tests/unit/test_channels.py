import json
from datetime import timedelta
from types import SimpleNamespace

from app.channels.gateway import _widget_notes
from app.channels.telegram_format import LIMIT, render_messages, split_markdown, to_telegram_html
from app.core.crypto import decrypt, encrypt
from app.services.channel_service import ChannelService, _now, hash_code, new_code


def test_crypto_roundtrip_and_not_plaintext():
    enc = encrypt("123:ABC-secret")
    assert "secret" not in enc and decrypt(enc) == "123:ABC-secret"


def test_html_escapes_and_formats():
    out = to_telegram_html("# 제목\n**굵게** `a<b` [링크](https://x.com/?a=1&b=2)\n<script>x</script>")
    assert "<b>제목</b>" in out and "<b>굵게</b>" in out and "<code>a&lt;b</code>" in out
    assert 'href="https://x.com/?a=1&amp;b=2"' in out and "&lt;script&gt;" in out


def test_table_and_code_become_pre():
    out = to_telegram_html("| a | b |\n|---|---|\n| 1 | 2 |\n```py\nx<1\n```")
    assert "<pre>| a | b |\n| 1 | 2 |</pre>" in out and "<pre>x&lt;1</pre>" in out


def test_split_keeps_fences_balanced_and_under_limit():
    chunks = split_markdown("```py\n" + "x=1\n" * 2000 + "```\nend")
    assert len(chunks) > 1 and all(c.count("```") % 2 == 0 for c in chunks[:-1])
    for html_text, plain in render_messages("긴 문장 " * 3000):
        assert len(html_text) <= LIMIT and len(plain) <= LIMIT


def _acc(code: str, ttl: int = 600):
    return SimpleNamespace(pair_code_hash=hash_code(code), pair_expires_at=_now() + timedelta(seconds=ttl),
                           external_user_id=None, chat_id=None, status="pending", last_error=None)


def test_pairing_is_one_time_case_insensitive_and_expires():
    code = new_code()
    acc = _acc(code)
    assert not ChannelService.try_pair(acc, "WRONG000", 1, 1) and acc.external_user_id is None
    assert ChannelService.try_pair(acc, code.lower(), 42, 99)
    assert (acc.external_user_id, acc.chat_id, acc.status, acc.pair_code_hash) == (42, 99, "connected", None)
    assert not ChannelService.try_pair(acc, code, 7, 7)  # 이미 사용됨
    assert not ChannelService.try_pair(_acc(code, ttl=-1), code, 1, 1)  # 만료


def test_widget_notes_dedupe_table_and_point_charts_to_web():
    step = lambda w: {"type": "tool_result", "tool": "create_widget", "output": json.dumps({"ok": True, "widget": w})}
    table = step({"type": "table", "spec": {"columns": ["a"], "rows": [[1]]}})
    chart = step({"type": "chart", "title": "추이", "spec": {}})
    assert "| a |" in _widget_notes([table], "표 없는 답변")
    assert _widget_notes([table], "| x |\n|---|\n| 1 |") == ""  # 본문에 표가 있으면 중복 출력하지 않는다
    assert "웹에서" in _widget_notes([chart], "답")


async def test_gate_blocks_until_approved_and_skips_safe_tools():
    from langchain_core.tools import StructuredTool

    from app.channels.approval import DENIED, gate_tools

    ran = []

    async def run(command: str = "") -> str:
        ran.append(command)
        return "ok"

    risky = StructuredTool.from_function(coroutine=run, name="exec_command", description="d")
    safe = StructuredTool.from_function(coroutine=run, name="web_search", description="d")
    asked = []

    async def deny(name, summary):
        asked.append((name, summary))
        return False

    gate_tools([risky, safe], deny)
    assert await risky.ainvoke({"command": "rm x"}) == DENIED and ran == []
    assert asked[0][0] == "exec_command" and "rm x" in asked[0][1]
    assert await safe.ainvoke({"command": "q"}) == "ok" and ran == ["q"] and len(asked) == 1  # 읽기 도구는 묻지 않는다

    async def allow(name, summary):
        return True

    gate_tools([risky], allow)  # 이미 감싼 도구는 다시 감싸지 않는다
    assert await risky.ainvoke({"command": "ls"}) == DENIED

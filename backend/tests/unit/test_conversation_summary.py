from types import SimpleNamespace

from app.services.conversation_summary import _transcript, pending_messages, summary_context


def msgs(n):
    return [SimpleNamespace(role="user" if i % 2 == 0 else "assistant", content=f"m{i}") for i in range(n)]


def test_pending_messages_only_those_outside_window_and_not_summarized():
    m = msgs(30)
    assert [x.content for x in pending_messages(m, 0, window=20)] == [f"m{i}" for i in range(10)]
    assert [x.content for x in pending_messages(m, 6, window=20)] == [f"m{i}" for i in range(6, 10)]
    assert pending_messages(m, 10, window=20) == []
    assert pending_messages(msgs(15), 0, window=20) == []  # 창 안에 다 들어오면 요약할 것이 없다
    assert pending_messages(m, 99, window=20) == []


def test_summary_context_only_for_long_conversations():
    assert summary_context("요약", 20, window=20) == ""
    assert summary_context(None, 50, window=20) == ""
    assert "앞부분 요약" in summary_context("- 코드명 BLUEFOX", 21, window=20)


def test_transcript_skips_error_placeholders_and_clips():
    m = [SimpleNamespace(role="user", content="질문"), SimpleNamespace(role="assistant", content="__error__"),
         SimpleNamespace(role="assistant", content="가" * 5000), SimpleNamespace(role="system", content="x")]
    t = _transcript(m)
    assert "__error__" not in t and "system" not in t and "…(생략)" in t and len(t) < 1700

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.agent.memory import ConversationMemory
from app.api.sandbox import _safe_relative_path
from app.schemas.chat import Reference
from app.services import reference_service as rs
from app.services.attachment_service import compose_with_attachments, validate_attachments


def run(c):
    return asyncio.run(c)


# ── 첨부: 폴더 ────────────────────────────────────────────────────────────────
def test_folder_attachment_is_kept_and_described():
    atts = validate_attachments([{"path": "/workspace/uploads/docs", "size": 2048, "kind": "folder", "file_count": 7},
                                 {"path": "/workspace/uploads/a.txt", "size": 10}])
    assert atts[0] == {"name": "docs", "path": "/workspace/uploads/docs", "size": 2048, "kind": "folder", "file_count": 7}
    assert "kind" not in atts[1]
    text = compose_with_attachments("봐줘", atts)
    assert "/workspace/uploads/docs/ (폴더, 파일 7개, 2.0 KB)" in text and "- /workspace/uploads/a.txt (10 B)" in text
    with pytest.raises(HTTPException):  # 업로드 폴더 밖은 거부
        validate_attachments([{"path": "/etc", "kind": "folder"}])


def test_folder_upload_paths_are_sanitized():
    assert _safe_relative_path("proj/src/main.py") == ["proj", "src", "main.py"]
    assert _safe_relative_path("proj\\src\\x.txt") == ["proj", "src", "x.txt"]
    for bad in ("proj/../../etc/passwd", "../x", "", "/", "a/" + "/".join(["d"] * 12) + "/f"):
        with pytest.raises(HTTPException):
            _safe_relative_path(bad)


# ── 참조 조립 ──────────────────────────────────────────────────────────────────
REFS = [{"type": "page", "id": "p1", "title": "회의록", "text": "내용A"}, {"type": "conversation", "id": "c1", "title": "지난 대화", "text": "사용자: 안녕"}]


def test_compose_note_and_public_refs():
    assert rs.compose_with_references("질문", None) == "질문"
    out = rs.compose_with_references("질문", REFS)
    assert out.startswith("질문") and "### 페이지: 회의록\n내용A" in out and "### 이전 대화: 지난 대화" in out and "지시문" in out
    assert rs.reference_note(REFS) == "[참조: 회의록, 지난 대화]" and rs.reference_note(None) == ""
    assert rs.public_refs(REFS) == [{"type": "page", "id": "p1", "title": "회의록"}, {"type": "conversation", "id": "c1", "title": "지난 대화"}]


def msg(role, content, meta=None):
    return SimpleNamespace(role=role, content=content, metadata_=meta or {})


def test_only_the_message_being_processed_carries_full_reference_text():
    db = [msg("user", "첫 질문", {"references": REFS}), msg("assistant", "답"), msg("user", "둘째", {"references": REFS})]
    h = ConversationMemory.from_db_messages(db).get_messages()
    assert "[참조: 회의록, 지난 대화]" in h[0].content and "내용A" not in h[0].content  # 지난 턴은 제목만
    assert "내용A" in h[2].content  # 마지막(처리 중) 메시지는 본문 전체
    # chat.py 가 만드는 user_input 과 같아야 한다 (stream_team 이 마지막 사용자 메시지 중복을 걸러내는 기준)
    assert h[2].content == rs.compose_with_references(compose_with_attachments("둘째", None), REFS)


# ── 참조 해석 (소유자 확인) ─────────────────────────────────────────────────────
class FakeDB:
    def __init__(self, page=None, conv=None):
        self.page, self.conv = page, conv

    async def execute(self, *_a, **_k):
        return SimpleNamespace(scalar_one_or_none=lambda: self.page)

    async def get(self, _model, _id):
        return self.conv


def ref(t, i): return Reference(type=t, id=i)


def test_page_reference_requires_ownership_and_clips(monkeypatch):
    monkeypatch.setattr(rs.settings, "REFERENCE_MAX_CHARS", 20)
    page = SimpleNamespace(title="", content="가" * 100)
    out = run(rs.resolve_references("u1", [ref("page", "p"), ref("page", "p")], FakeDB(page=page)))
    assert len(out) == 1 and out[0]["title"] == "제목 없음" and out[0]["text"].endswith("(이하 생략)")
    with pytest.raises(HTTPException) as e:
        run(rs.resolve_references("u1", [ref("page", "p")], FakeDB(page=None)))
    assert e.value.status_code == 404


def test_conversation_reference_skips_errors_current_and_foreign(monkeypatch):
    conv = SimpleNamespace(user_id="u1", is_test=False, title="지난 대화")

    async def msgs(cid, db):
        return [msg("user", "질문1"), msg("assistant", "__error__"), msg("assistant", "답1"), msg("system", "무시")]

    monkeypatch.setattr(rs.ChatService, "get_messages", staticmethod(msgs))
    out = run(rs.resolve_references("u1", [ref("conversation", "c1")], FakeDB(conv=conv), current_conversation_id="cur"))
    assert out[0]["text"] == "사용자: 질문1\n\n에이전트: 답1"
    assert run(rs.resolve_references("u1", [ref("conversation", "cur")], FakeDB(conv=conv), current_conversation_id="cur")) == []
    for bad in (SimpleNamespace(user_id="other", is_test=False, title="x"), SimpleNamespace(user_id="u1", is_test=True, title="x"), None):
        with pytest.raises(HTTPException):
            run(rs.resolve_references("u1", [ref("conversation", "c9")], FakeDB(conv=bad)))


def test_reference_count_limit():
    with pytest.raises(HTTPException) as e:
        run(rs.resolve_references("u1", [ref("page", str(i)) for i in range(rs.MAX_REFERENCES + 1)], FakeDB()))
    assert e.value.status_code == 400

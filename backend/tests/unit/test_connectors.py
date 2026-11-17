"""Google Workspace 커넥터: OAuth 상태·범위, 도구의 파싱과 안전 규칙."""
import base64
import time
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import settings
from app.services import connector_service as cs
from app.tools import google_tools as gt


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def test_catalog_has_exactly_the_six_google_connectors():
    assert list(cs.CONNECTORS) == ["gmail", "google_calendar", "google_drive", "google_docs", "google_sheets", "google_slides"]
    # Gmail·Drive·Docs·Sheets·Slides 는 읽기 전용 범위, Calendar 만 일정 쓰기 범위
    writes = [c for c, v in cs.CONNECTORS.items() if any(not s.endswith("readonly") for s in v["scopes"])]
    assert writes == ["google_calendar"]
    assert set(gt.TOOL_BY_CONNECTOR) == set(cs.CONNECTORS) and len(gt.CONNECTOR_TOOL_NAMES) == 6


def test_state_roundtrip_expiry_and_tampering(monkeypatch):
    s = cs.make_state("u1", "gmail")
    assert cs.read_state(s) == ("u1", "gmail")
    with pytest.raises(cs.ConnectorError):
        cs.read_state(s[:-4] + "abcd")  # 위·변조
    with pytest.raises(cs.ConnectorError):
        cs.read_state("not-a-state")
    real = time.time()
    monkeypatch.setattr(cs.time, "time", lambda: real + cs.STATE_TTL + 5)
    with pytest.raises(cs.ConnectorError):
        cs.read_state(s)  # 만료


def test_auth_url_requests_incremental_scopes(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://localhost:8500/")
    granted = "https://www.googleapis.com/auth/gmail.readonly"
    url = cs.build_auth_url("u1", "google_calendar", granted)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    scopes = q["scope"].split()
    assert "openid" in scopes and "email" in scopes
    assert granted in scopes and "https://www.googleapis.com/auth/calendar.events" in scopes  # 이미 허용한 범위 + 새 범위
    assert q["access_type"] == "offline" and q["include_granted_scopes"] == "true"
    assert q["redirect_uri"] == "http://localhost:8500/api/connectors/google/callback"
    assert cs.read_state(q["state"]) == ("u1", "google_calendar")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
    with pytest.raises(cs.ConnectorError):
        cs.build_auth_url("u1", "gmail")  # 설정이 없으면 시작하지 않는다


def test_gmail_body_prefers_plain_text_and_lists_attachments_by_name():
    msg = {"payload": {"mimeType": "multipart/mixed", "parts": [
        {"mimeType": "multipart/alternative", "parts": [
            {"mimeType": "text/plain", "body": {"data": b64("안녕하세요 본문입니다")}},
            {"mimeType": "text/html", "body": {"data": b64("<p>HTML 본문</p>")}},
        ]},
        {"mimeType": "application/pdf", "filename": "견적서.pdf", "body": {"size": 1234, "attachmentId": "x"}},
    ]}}
    body, atts = gt.gmail_body(msg)
    assert body == "안녕하세요 본문입니다" and atts == ["견적서.pdf (application/pdf, 1234바이트)"]
    html_only = {"payload": {"mimeType": "text/html", "body": {"data": b64("<div>첫줄<br>둘째줄 &amp; 셋째</div><script>x()</script>")}}}
    text, _ = gt.gmail_body(html_only)
    assert "첫줄" in text and "둘째줄 & 셋째" in text and "x()" not in text


def test_drive_query_building():
    assert gt.drive_query("진라면") == "(name contains '진라면' or fullText contains '진라면') and trashed = false"
    assert gt.drive_query("o'neil", gt.MIME["docs"]).startswith("(name contains 'o\\'neil'")
    assert gt.drive_query("name contains 'x' and modifiedTime > '2026-01-01'") == "(name contains 'x' and modifiedTime > '2026-01-01') and trashed = false"  # Drive 문법은 그대로
    assert "mimeType = 'application/vnd.google-apps.spreadsheet'" in gt.drive_query("", gt.MIME["sheets"])


def test_docs_and_slides_text_extraction():
    doc = {"body": {"content": [
        {"paragraph": {"elements": [{"textRun": {"content": "제목\n"}}]}},
        {"table": {"tableRows": [{"tableCells": [{"content": [{"paragraph": {"elements": [{"textRun": {"content": "A"}}]}}]},
                                                 {"content": [{"paragraph": {"elements": [{"textRun": {"content": "B"}}]}}]}]}]}},
    ]}}
    assert gt.doc_text(doc) == "제목\nA | B"
    pres = {"slides": [{"pageElements": [{"shape": {"text": {"textElements": [{"textRun": {"content": "발표 제목\n"}}]}}}]}]}
    assert "## 슬라이드 1\n발표 제목" in gt.slides_text(pres)
    assert gt.sheet_tsv([["a", 1], ["b", 2]]) == "a\t1\nb\t2"


@pytest.mark.asyncio
async def test_calendar_write_is_blocked_without_a_user_screen_and_never_notifies_by_default(monkeypatch):
    calls = []

    async def fake_api(user_id, method, url, **kw):
        calls.append((method, url, kw))
        return {"id": "e1", "summary": "회의", "start": {"dateTime": "2026-11-12T15:00:00+09:00"}, "end": {"dateTime": "2026-11-12T16:00:00+09:00"}}

    monkeypatch.setattr(gt, "google_api", fake_api)
    ro = gt.CalendarTool(user_id="u1", allow_write=False)
    out = await ro._arun(action="create_event", summary="회의", start="2026-11-12T15:00:00+09:00", end="2026-11-12T16:00:00+09:00")
    assert out.startswith("Error") and not calls  # 예약·메신저 실행은 조회만
    rw = gt.CalendarTool(user_id="u1")
    out = await rw._arun(action="create_event", summary="회의", start="2026-11-12T15:00:00+09:00", end="2026-11-12T16:00:00+09:00", attendees=["a@x.com"])
    method, url, kw = calls[-1]
    assert method == "POST" and kw["params"]["sendUpdates"] == "none"  # 초대 메일은 명시했을 때만
    assert kw["json"]["attendees"] == [{"email": "a@x.com"}] and "일정을 만들었습니다" in out
    await rw._arun(action="delete_event", event_id="e1", notify_attendees=True)
    assert calls[-1][2]["params"]["sendUpdates"] == "all"
    assert gt._when("2026-11-12") == {"date": "2026-11-12"} and gt._when("2026-11-12T15:00:00")["timeZone"] == "Asia/Seoul"


@pytest.mark.asyncio
async def test_tools_report_connector_errors_as_text(monkeypatch):
    async def boom(*a, **k):
        raise cs.ConnectorError("Google 계정이 연결돼 있지 않습니다.")

    monkeypatch.setattr(gt, "google_api", boom)
    assert (await gt.GmailTool(user_id="u")._arun(action="search", query="x")).startswith("Error: Google 계정")
    assert "Error" in await gt.DriveTool(user_id="u")._arun(action="read", file_id="f")


def test_connector_tools_reach_the_team_leader():
    from app.agent.agno_engine import LEADER_TOOLS

    assert gt.CONNECTOR_TOOL_NAMES <= LEADER_TOOLS  # 팀 리더에게 없으면 모델이 도구를 볼 수 없다


class _Resp:
    def __init__(self, status, data):
        self.status_code, self._d, self.text, self.content = status, data, str(data), b"x"

    def json(self):
        return self._d


@pytest.mark.asyncio
async def test_complete_oauth_stores_encrypted_tokens_and_merges_connectors(monkeypatch):
    from app.core import crypto
    from app.models.connector_account import ConnectorAccount

    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "sec")
    gmail_scope = cs.CONNECTORS["gmail"]["scopes"][0]
    cal_scopes = cs.CONNECTORS["google_calendar"]["scopes"]
    replies = [
        _Resp(200, {"access_token": "AT1", "refresh_token": "RT1", "expires_in": 3600, "scope": f"openid email {gmail_scope}"}),
        _Resp(200, {"email": "me@example.com"}),
        _Resp(200, {"access_token": "AT2", "expires_in": 3600, "scope": f"openid email {gmail_scope} {' '.join(cal_scopes)}"}),  # 재동의: refresh token 없음
        _Resp(200, {"email": "me@example.com"}),
    ]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return replies.pop(0)

        async def get(self, *a, **k):
            return replies.pop(0)

    monkeypatch.setattr(cs.httpx, "AsyncClient", FakeClient)
    store: dict = {}

    class FakeDb:
        def add(self, o):
            store["acc"] = o

        async def commit(self):
            pass

    async def fake_account(user_id, db):
        return store.get("acc")

    monkeypatch.setattr(cs.ConnectorService, "account", staticmethod(fake_account))
    await cs.ConnectorService.complete_oauth("code1", cs.make_state("u1", "gmail"), FakeDb())
    acc: ConnectorAccount = store["acc"]
    assert acc.connectors == ["gmail"] and acc.email == "me@example.com"
    assert acc.refresh_token_enc and "RT1" not in acc.refresh_token_enc and crypto.decrypt(acc.refresh_token_enc) == "RT1"  # 암호화 저장
    await cs.ConnectorService.complete_oauth("code2", cs.make_state("u1", "google_calendar"), FakeDb())
    assert acc.connectors == ["gmail", "google_calendar"]
    assert crypto.decrypt(acc.refresh_token_enc) == "RT1"  # 재동의에 refresh token 이 없어도 기존 것을 유지
    assert gmail_scope in acc.scopes and cal_scopes[0] in acc.scopes


@pytest.mark.asyncio
async def test_complete_oauth_rejects_partial_consent(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "sec")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Resp(200, {"access_token": "AT", "refresh_token": "RT", "scope": "openid email"})  # 필요한 범위를 허용하지 않음

        async def get(self, *a, **k):
            return _Resp(200, {"email": "x@y.com"})

    monkeypatch.setattr(cs.httpx, "AsyncClient", FakeClient)
    with pytest.raises(cs.ConnectorError, match="권한"):
        await cs.ConnectorService.complete_oauth("c", cs.make_state("u1", "gmail"), object())

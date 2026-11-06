import gzip
import io
import tarfile
import time

from app.services import app_auth
from app.services.app_policy import RateLimiter, decide_publish, host_slug, make_slug, public_url, scan_artifact


def test_slug_and_public_url_and_host(monkeypatch):
    assert make_slug("My Todo App!", "3f9a12bc-0000") == "my-todo-app-3f9a12"
    assert make_slug("할 일", "3f9a12bc-0000") == "app-3f9a12"
    assert public_url("x-1").startswith("http://x-1.localhost:")
    assert host_slug("my-todo-3f9a12.localhost:20100") == "my-todo-3f9a12"
    assert host_slug("localhost:20100") is None
    assert host_slug("a.b.localhost") is None  # 단계가 더 깊은 호스트는 거부
    assert host_slug("evil.example.com") is None
    assert host_slug("My-App-1.LOCALHOST") == "my-app-1"


def _gz(tmp_path, files):
    p = tmp_path / "a.tar.gz"
    with gzip.open(p, "wb") as g, tarfile.open(fileobj=g, mode="w") as t:
        for name, data in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return str(p)


def test_scan_artifact(tmp_path):
    clean = _gz(tmp_path, {"index.html": b"<h1>hi</h1>", "node_modules/x/.env": b"A=1"})
    assert scan_artifact(clean) == []
    bad = _gz(tmp_path, {"index.html": b"x", ".env": b"K=1", "app.js": b"const k='sk-abcdefghijklmnopqrstuvwxyz123456'", "img.bin": b"\0\0sk-abcdefghijklmnopqrstuvwxyz1234"})
    issues = scan_artifact(bad)
    assert any(".env" in i for i in issues) and any("sk-" in i for i in issues) and len(issues) == 2


def test_decide_publish():
    assert decide_publish("static", [])[0] == "approved"
    assert decide_publish("server", [])[0] == "pending"
    assert decide_publish("static", ["키"])[0] == "blocked"


def test_rate_limiter():
    r = RateLimiter(3, 60)
    assert [r.allow("a") for _ in range(4)] == [True, True, True, False]
    assert r.allow("b")
    assert RateLimiter(0).allow("x")


def test_ticket_and_session(monkeypatch):
    t = app_auth.make_ticket("app1", "u1")
    assert not app_auth.check_ticket(t, "app2", "u1")   # 다른 앱
    assert not app_auth.check_ticket(t, "app1", "u2")   # 다른 사용자
    assert not app_auth.check_ticket(t + "x", "app1", "u1")  # 변조
    assert app_auth.check_ticket(t, "app1", "u1")
    assert not app_auth.check_ticket(t, "app1", "u1")   # 일회용
    s = app_auth.make_session("app1", "u1", 3)
    assert app_auth.check_session(s, "app1", "u1", 3)
    assert not app_auth.check_session(s, "app1", "u1", 4)  # 에폭이 올라가면 무효
    assert not app_auth.check_session(t, "app1", "u1", 0)  # 종류가 다름
    monkeypatch.setattr(app_auth, "TICKET_TTL", -1)
    assert not app_auth.check_ticket(app_auth.make_ticket("app1", "u1"), "app1", "u1")  # 만료


def test_review_ticket_and_session():
    t = app_auth.make_review_ticket("a1", "rev")
    assert not app_auth.check_review_ticket(t, "a2")
    assert app_auth.check_review_ticket(t, "a1")
    assert not app_auth.check_review_ticket(t, "a1")  # 일회용
    s = app_auth.make_review_session("a1")
    assert app_auth.check_review_session(s, "a1") and not app_auth.check_review_session(s, "a2")
    assert not app_auth.check_session(s, "a1", "rev", 0)  # 검수 세션으로 소유자 세션을 대신할 수 없다
    assert not app_auth.check_review_ticket(app_auth.make_ticket("a1", "rev"), "a1")  # 소유자 티켓으로 검수할 수 없다

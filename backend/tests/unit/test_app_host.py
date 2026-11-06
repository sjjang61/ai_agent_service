from types import SimpleNamespace as N

from app.services.app_gateway import _fwd_headers, _rewrite_location, _strip_token
from app.services.app_host import AppHost, pick_port


def test_pick_port_lowest_free_and_exhausted():
    assert pick_port({20000, 20001}, 20000, 20003) == 20002
    assert pick_port(set(), 20000, 20003, is_free=lambda p: p >= 20002) == 20002
    assert pick_port({20000, 20001}, 20000, 20001) is None


def test_strip_token_and_location_rewrite():
    req = N(query_params=N(multi_items=lambda: [("t", "x"), ("a", "1"), ("a", "2")]), url=N(scheme="http"), headers={"host": "h:20001"})
    assert _strip_token(req) == "a=1&a=2"
    st = N(container_port=5173, upstream=40000)
    assert _rewrite_location("http://localhost:5173/login", req, st) == "http://h:20001/login"
    assert _rewrite_location("http://127.0.0.1:40000/x", req, st) == "http://h:20001/x"
    assert _rewrite_location("https://other.example/x", req, st) == "https://other.example/x"


def test_session_cookies_not_forwarded_to_apps():
    req = N(headers={"cookie": "appsess_20001=sig; sid=abc; appsess_20002=zzz", "host": "h", "accept": "*/*"}, url=N(scheme="http"), client=N(host="1.2.3.4"))
    h = _fwd_headers(req, N(container_port=5173))
    assert h["cookie"] == "sid=abc" and h["host"] == "localhost:5173" and h["x-forwarded-for"] == "1.2.3.4"


def test_public_ok_requires_public_and_approved():
    mk = lambda v, m: N(visibility=v, moderation=m)
    assert AppHost.public_ok(mk("public", "approved"))
    assert not AppHost.public_ok(mk("public", "pending"))
    assert not AppHost.public_ok(mk("public", "suspended"))
    assert not AppHost.public_ok(mk("private", "approved"))

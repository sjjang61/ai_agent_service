from types import SimpleNamespace as N

from app.services.app_gateway import _rewrite_location, _strip_token, token_ok
from app.services.app_host import pick_port


def test_pick_port_lowest_free_and_exhausted():
    assert pick_port({20000, 20001}, 20000, 20003) == 20002
    assert pick_port(set(), 20000, 20003, is_free=lambda p: p >= 20002) == 20002
    assert pick_port({20000, 20001}, 20000, 20001) is None


def test_token_ok():
    open_app = N(require_token=False, token="s3cret")
    priv = N(require_token=True, token="s3cret")
    assert token_ok(open_app, None, None)
    assert not token_ok(priv, None, None)
    assert not token_ok(priv, "wrong", "also-wrong")
    assert token_ok(priv, "s3cret", None) and token_ok(priv, None, "s3cret") and token_ok(priv, None, None, "s3cret")


def test_strip_token_and_location_rewrite():
    req = N(query_params=N(multi_items=lambda: [("t", "x"), ("a", "1"), ("a", "2")]), url=N(scheme="http"), headers={"host": "h:20001"})
    assert _strip_token(req) == "a=1&a=2"
    st = N(container_port=5173, upstream=40000)
    assert _rewrite_location("http://localhost:5173/login", req, st) == "http://h:20001/login"
    assert _rewrite_location("http://127.0.0.1:40000/x", req, st) == "http://h:20001/x"
    assert _rewrite_location("https://other.example/x", req, st) == "https://other.example/x"

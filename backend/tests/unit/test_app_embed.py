"""앱 응답 헤더: 서비스 화면의 iframe 에서만 열리게 (X-Frame-Options 제거 + CSP frame-ancestors)"""
from app.config import settings
from app.services.app_gateway import embed_headers


def test_x_frame_options_removed_and_ancestors_added():
    h = embed_headers({"X-Frame-Options": "SAMEORIGIN", "content-type": "text/html"})
    assert not any(k.lower() == "x-frame-options" for k in h)
    csp = h["content-security-policy"]
    assert csp.startswith("frame-ancestors 'self'")
    assert all(o in csp for o in settings.CORS_ORIGINS)


def test_existing_csp_keeps_other_directives_and_replaces_frame_ancestors():
    h = embed_headers({"content-security-policy": "default-src 'self'; frame-ancestors 'none'; object-src 'none'", "x-frame-options": "DENY"})
    csp = h["content-security-policy"]
    assert "default-src 'self'" in csp and "object-src 'none'" in csp
    assert csp.count("frame-ancestors") == 1 and "frame-ancestors 'none'" not in csp
    assert "x-frame-options" not in {k.lower() for k in h}


def test_wildcard_origin_is_not_echoed(monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", ["*", "http://a.example"])
    csp = embed_headers({})["content-security-policy"]
    assert "*" not in csp and "http://a.example" in csp

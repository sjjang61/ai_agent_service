import asyncio
import base64
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import object_storage
from app.tools import image_tools
from app.tools.image_tools import GenerateImageTool, UploadToMinioTool

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20


class _FakeImages:
    def __init__(self, calls):
        self.calls = calls

    async def generate(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG).decode())], usage=None)


@pytest.fixture
def env(monkeypatch):
    calls, uploads, writes = [], [], []
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "k")
    monkeypatch.setattr(settings, "IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_IMAGE_MODEL", "test-image-model")
    monkeypatch.setattr(settings, "IMAGE_DAILY_LIMIT", 2)
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(settings, "MINIO_ACCESS_KEY", "a")
    monkeypatch.setattr(settings, "MINIO_SECRET_KEY", "s")
    monkeypatch.setattr(settings, "MINIO_PUBLIC_URL", "http://pub.test")
    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kw: SimpleNamespace(images=_FakeImages(calls)))

    async def fake_upload(data, key, content_type="application/octet-stream"):
        uploads.append((key, content_type, len(data)))
        return object_storage.public_url(key)

    class FakeManager:
        async def write_file(self, cid, path, data, mode=0o644):
            writes.append(path)

        async def read_file(self, cid, path, max_bytes):
            return PNG if path.endswith(".png") else b"<svg onload=alert(1)>", 0o644

    async def fake_container(user_id, sandbox_cid=""):
        return "cid"

    monkeypatch.setattr(object_storage, "upload_public", fake_upload)
    monkeypatch.setattr(image_tools, "_manager", lambda: FakeManager())
    monkeypatch.setattr(image_tools, "_container", fake_container)
    image_tools._daily.clear()
    return SimpleNamespace(calls=calls, uploads=uploads, writes=writes)


def run(tool, **kw):
    return asyncio.run(tool._arun(**kw))


def test_generate_saves_uploads_and_returns_markdown(env):
    out = run(GenerateImageTool(user_id="u1234567890"), prompt="푸른 바다의 일출", quality="low", size="1536x1024")
    assert env.calls[0]["model"] == "test-image-model" and env.calls[0]["size"] == "1536x1024" and env.calls[0]["quality"] == "low"
    assert env.writes[0].startswith("/workspace/images/") and env.writes[0].endswith(".png")
    key, ctype, n = env.uploads[0]
    assert key.startswith("images/u1234567/") and ctype == "image/png" and n == len(PNG)
    assert f"http://pub.test/{settings.MINIO_PUBLIC_BUCKET}/images/" in out and "![" in out and "Public URL:" in out


def test_generate_without_upload_keeps_workspace_only(env):
    out = run(GenerateImageTool(user_id="u1"), prompt="p", upload=False)
    assert not env.uploads and "Public URL" not in out and "/workspace/images/" in out


def test_daily_limit_and_errors(env):
    t = GenerateImageTool(user_id="u1")
    run(t, prompt="a"); run(t, prompt="b")
    assert run(t, prompt="c").startswith("Error: 오늘의 이미지 생성 한도")
    assert len(env.calls) == 2                                              # 한도 초과는 API 를 부르지 않는다
    assert run(GenerateImageTool(user_id="u2"), prompt=" ").startswith("Error")


def test_generate_requires_configuration(env, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    assert run(GenerateImageTool(user_id="u"), prompt="p").startswith("Error: 이미지 생성이 설정")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "k")
    monkeypatch.setattr(settings, "MINIO_ENDPOINT", "")
    assert "MinIO" in run(GenerateImageTool(user_id="u"), prompt="p")


def test_upload_accepts_real_images_only(env):
    ok = run(UploadToMinioTool(user_id="u1234567890"), path="images/logo.png")
    assert "Public URL: http://pub.test/" in ok and env.uploads[0][1] == "image/png" and env.uploads[0][0].endswith("-logo.png")
    bad = run(UploadToMinioTool(user_id="u1"), path="x.svg")                 # 내용이 이미지가 아니면 확장자와 상관없이 거부
    assert bad.startswith("Error") and len(env.uploads) == 1
    assert run(UploadToMinioTool(user_id="u1"), path="../etc/passwd").startswith("Error")


def test_object_key_and_url_helpers():
    assert object_storage.safe_slug("푸른 바다 sunrise!") == "sunrise"
    assert object_storage.safe_slug("") == "file"
    k = object_storage.make_key("abcdef123456", "my pic.png", "images")
    assert k.startswith("images/abcdef12/") and k.endswith("-my_pic.png")


def test_drop_disabled_removes_only_disabled_tools():
    from app.services.tool_settings_service import drop_disabled

    tools = [SimpleNamespace(name=n) for n in ("a", "b", "c")]
    assert [t.name for t in drop_disabled(tools, {"b"})] == ["a", "c"]
    assert drop_disabled(tools, set()) is tools


# ── 동영상 ──────────────────────────────────────────────────────────────────
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\0" * 40


@pytest.fixture
def venv(env, monkeypatch):
    from app.tools import video_tools

    calls = []
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "g")
    monkeypatch.setattr(settings, "VIDEO_API_KEY", "")
    monkeypatch.setattr(settings, "VIDEO_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "VIDEO_DAILY_LIMIT", 2)

    async def fake_generate(prompt, seconds, ratio, res, refs=(), timeout=None):
        calls.append(dict(prompt=prompt, seconds=seconds, ratio=ratio, res=res, refs=len(refs)))
        return SimpleNamespace(content=MP4, model="m", seconds=seconds, meta={"resolution": res, "aspect_ratio": ratio})

    monkeypatch.setattr(video_tools, "generate_video", fake_generate)
    monkeypatch.setattr(video_tools, "_manager", image_tools._manager)
    monkeypatch.setattr(video_tools, "_container", image_tools._container)
    video_tools._daily.clear()
    return SimpleNamespace(calls=calls, tools=video_tools, base=env)


def test_video_generate_uploads_and_links(venv):
    out = run(venv.tools.GenerateVideoTool(user_id="u1234567890"), prompt="해변을 달리는 강아지", seconds=7, resolution="720p")
    c = venv.calls[0]
    assert c["seconds"] == 6 and c["res"] == "720p" and c["ratio"] == settings.VIDEO_ASPECT_RATIO     # 7초는 가장 가까운 6초로 보정
    assert venv.base.writes[0].startswith("/workspace/videos/") and venv.base.writes[0].endswith(".mp4")
    key, ctype, n = venv.base.uploads[0]
    assert key.startswith("videos/u1234567/") and ctype == "video/mp4" and n == len(MP4)
    assert "[영상 보기](http://pub.test/" in out and "Public URL:" in out


def test_video_reference_images_and_limits(venv):
    t = venv.tools.GenerateVideoTool(user_id="u1")
    run(t, prompt="a", reference_images=["images/a.png"])
    assert venv.calls[0]["refs"] == 1
    assert run(t, prompt="b", reference_images=["x.svg"]).startswith("Error: 참조 이미지")           # 이미지가 아니면 거부
    run(t, prompt="c")
    assert run(t, prompt="d").startswith("Error: 오늘의 동영상 생성 한도")                              # 한도 초과는 생성하지 않는다
    assert len(venv.calls) == 2


def test_video_requires_configuration(venv, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    assert run(venv.tools.GenerateVideoTool(user_id="u"), prompt="p").startswith("Error: 동영상 생성이 설정")
    monkeypatch.setattr(settings, "VIDEO_API_KEY", "vk")                       # 영상 전용 키가 있으면 GOOGLE_API_KEY 없이도 동작
    assert not run(venv.tools.GenerateVideoTool(user_id="u"), prompt="p").startswith("Error: 동영상 생성이 설정")


def test_upload_accepts_mp4_by_content(env):
    from app.tools import image_tools as it

    class VM:
        async def read_file(self, cid, path, max_bytes):
            return (MP4 if path.endswith(".mp4") else PNG), 0o644

        async def write_file(self, *a, **k): ...

    it._manager = lambda: VM()
    out = run(UploadToMinioTool(user_id="u1234567890"), path="videos/clip.mp4")
    assert "[영상 보기](http://pub.test/" in out and env.uploads[-1][1] == "video/mp4" and env.uploads[-1][0].startswith("videos/")


def test_video_service_helpers():
    from app.services import video_gen as vg

    assert vg.clamp_duration(1) == 4 and vg.clamp_duration(99) == 10 and vg.clamp_duration(9) == 8
    p = vg.build_prompt("고양이", 6, ref_count=2)
    assert "<IMAGE_REF_0>, <IMAGE_REF_1>" in p and "about 6 seconds" in p and "Avoid:" in p
    assert vg._refs_might_be_the_cause(Exception("invalid image mime")) and not vg._refs_might_be_the_cause(vg.VideoApiError(429, "quota"))


def test_find_video_uses_last_model_output():
    from app.services.video_gen import find_video

    resp = {"steps": [
        {"type": "user_input", "content": [{"type": "video", "data": "OLD"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "hi"}, {"type": "video", "data": "NEW", "mime_type": "video/mp4"}]},
    ]}
    assert find_video(resp)["data"] == "NEW"
    assert find_video({"steps": [{"type": "user_input", "content": []}]}) is None
    assert find_video({}) is None


def test_generate_video_posts_current_schema_and_decodes(monkeypatch):
    import base64
    import httpx

    from app.services import video_gen as vg

    seen = {}

    def handler(request: httpx.Request):
        import json

        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-goog-api-key"), json.loads(request.content)
        return httpx.Response(200, json={"status": "completed", "usage": {"total_tokens": 5}, "steps": [
            {"type": "user_input", "content": []},
            {"type": "model_output", "content": [{"type": "video", "data": base64.b64encode(MP4).decode(), "mime_type": "video/mp4"}]}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "VIDEO_API_KEY", "")  # .env 의 실제 키가 테스트에 섞이지 않게 한다
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "gk")
    monkeypatch.setattr(settings, "VIDEO_STRIP_AUDIO", False)
    monkeypatch.setattr(vg, "probe_seconds", lambda c: None)
    r = asyncio.run(vg.generate_video("고양이", 7, "16:9", "360p", [(PNG, "image/png")]))
    assert r.content == MP4 and r.seconds == 6 and r.meta["reference_images"] == 1
    b = seen["body"]
    assert seen["url"].endswith("/v1beta/interactions") and seen["key"] == "gk"
    assert b["input"][0]["type"] == "user_input" and [p["type"] for p in b["input"][0]["content"]] == ["image", "text"]
    assert b["response_format"] == {"type": "video", "resolution": "360p", "aspect_ratio": "16:9"} and b["background"] is False and b["store"] is False


def test_generate_video_retries_without_refs_only_when_refs_are_suspect(monkeypatch):
    import base64
    import httpx

    from app.services import video_gen as vg

    calls = []

    def handler(request: httpx.Request):
        import json

        parts = json.loads(request.content)["input"][0]["content"]
        calls.append(len(parts))
        if len(parts) > 1 and settings.GOOGLE_API_KEY == "bad-image":
            return httpx.Response(400, json={"error": {"message": "invalid image"}})
        if settings.GOOGLE_API_KEY == "quota":
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json={"steps": [{"type": "model_output", "content": [{"type": "video", "data": base64.b64encode(MP4).decode()}]}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(vg, "probe_seconds", lambda c: None)
    monkeypatch.setattr(settings, "VIDEO_API_KEY", "")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "bad-image")
    assert asyncio.run(vg.generate_video("p", 4, "16:9", "360p", [(PNG, "image/png")])).content == MP4
    assert calls == [2, 1]                                                  # 첨부 때문에 거절되면 첨부 없이 한 번 더
    calls.clear()
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "quota")
    with pytest.raises(vg.VideoGenerationError):
        asyncio.run(vg.generate_video("p", 4, "16:9", "360p", [(PNG, "image/png")]))
    assert calls == [2]                                                     # 쿼터 오류는 재시도하지 않는다


def test_artifact_classify_video():
    from app.services.artifact_service import classify

    assert classify("clip.MP4") == ("video", "video/mp4")
    assert classify("a/b.webm") == ("video", "video/webm") and classify("x.mov")[0] == "video"
    assert classify("pic.png")[0] == "image" and classify("notes.txt")[0] == "text" and classify("movie.avi")[0] == "other"

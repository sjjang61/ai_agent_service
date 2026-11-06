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

"""이미지 생성(generate_image)과 공개 업로드(upload_to_minio) 도구.

generate_image 는 OpenAI 이미지 모델(OPENAI_IMAGE_MODEL)로 그림을 만들어 sandbox /workspace/images/ 에 저장하고,
기본으로 공개 MinIO 버킷에 올려 공개 URL 까지 돌려준다. upload_to_minio 는 sandbox 의 이미지 파일 하나를 같은 방식으로 올린다.
(생성과 업로드는 같은 모듈 app.services.object_storage 를 쓰며, 업로드만 따로 부를 수도 있다.)
"""
import asyncio
import base64
import logging
import re
import time
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.services import object_storage
from app.tools.workspace_tools import (
    WORKSPACE, _AsyncTool, _container, _fmt_err, _image_format, _manager, resolve_path,
)

logger = logging.getLogger(__name__)

IMAGES_DIR = f"{WORKSPACE}/images"
SIZES = ("1024x1024", "1536x1024", "1024x1536", "auto")
QUALITIES = ("low", "medium", "high", "auto")
MIME = {"png": "image/png", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
EXT = {"png": "png", "jpeg": "jpg", "gif": "gif", "webp": "webp"}

# (user_id, 날짜) → 오늘 생성 횟수. 프로세스 메모리라 서버를 다시 시작하면 초기화된다.
_daily: dict[tuple[str, date], int] = {}


def _limit_reached(user_id: str) -> bool:
    limit = settings.IMAGE_DAILY_LIMIT
    return bool(limit) and _daily.get((user_id, date.today()), 0) >= limit


def _count(user_id: str) -> None:
    today = date.today()
    for k in [k for k in _daily if k[1] != today]:
        del _daily[k]
    _daily[(user_id, today)] = _daily.get((user_id, today), 0) + 1


def _result_text(path: Optional[str], url: Optional[str], alt: str) -> str:
    lines = []
    if path:
        lines.append(f"Saved in workspace: {path}")
    if url:
        alt = " ".join(alt.split())[:80].replace("[", "(").replace("]", ")")
        lines.append(f"Public URL: {url}")
        lines.append(f"Show it to the user in your answer with this markdown: ![{alt}]({url})")
    return "\n".join(lines)


# ── generate_image ───────────────────────────────────────────────────────────
class GenerateImageInput(BaseModel):
    prompt: str = Field(description="Detailed description of the image to create (subject, style, composition, colors, text to render). Any language")
    size: Optional[Literal["1024x1024", "1536x1024", "1024x1536", "auto"]] = Field(
        default=None, description="Image size: 1024x1024 (square, default), 1536x1024 (landscape), 1024x1536 (portrait) or auto"
    )
    quality: Optional[Literal["low", "medium", "high", "auto"]] = Field(
        default=None, description="Quality: low is fast and cheap (drafts), high is slow and costly. Omit for the model default"
    )
    filename: Optional[str] = Field(default=None, description="Short file name without extension (letters, digits, - _). Optional")
    upload: bool = Field(default=True, description="Upload to the public MinIO bucket and return a public URL (default true)")


class GenerateImageTool(_AsyncTool):
    name: str = "generate_image"
    description: str = (
        "Generate a NEW image from a text description with an image model (illustrations, posters, logos, concept art, mockups). "
        "Saves the PNG in /workspace/images/ and, by default, uploads it to MinIO and returns a public URL. "
        "In your final answer show the image with the returned markdown `![...](url)`. "
        "Costs money and takes 20-90 seconds, so generate only what the user asked for (usually one image). "
        "Do not use it for charts or diagrams of data (use code) or to edit an existing image."
    )
    args_schema: type[BaseModel] = GenerateImageInput
    conversation_id: str = ""

    async def _arun(self, prompt: str, size: Optional[str] = None, quality: Optional[str] = None,
                    filename: Optional[str] = None, upload: bool = True) -> str:
        if not settings.IMAGE_GENERATION_ENABLED or not settings.OPENAI_API_KEY:
            return "Error: 이미지 생성이 설정되어 있지 않습니다 (IMAGE_GENERATION_ENABLED, OPENAI_API_KEY)"
        if upload and not object_storage.enabled():
            return "Error: 공개 업로드(MinIO)가 설정되어 있지 않습니다. upload=false 로 workspace 에만 저장하거나 관리자에게 MinIO 설정을 요청하세요"
        if not prompt.strip():
            return "Error: prompt 가 비어 있습니다"
        if _limit_reached(self.user_id):
            return f"Error: 오늘의 이미지 생성 한도({settings.IMAGE_DAILY_LIMIT}장)에 도달했습니다. 내일 다시 시도해 주세요"
        size = size if size in SIZES else settings.IMAGE_DEFAULT_SIZE
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.IMAGE_TIMEOUT_SECONDS)
            params = dict(model=settings.OPENAI_IMAGE_MODEL, prompt=prompt[:4000], n=1, size=size)
            if quality and quality != "auto":
                params["quality"] = quality
            resp = await client.images.generate(**params)
            b64 = resp.data[0].b64_json or ""
            if not b64:
                return "Error: 이미지 모델이 이미지를 돌려주지 않았습니다"
            data = base64.b64decode(b64)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "moderation" in msg.lower() or "safety" in msg.lower():
                return "Error: 안전 정책에 걸려 이미지를 만들지 못했습니다. 요청 내용을 바꿔 다시 시도하세요"
            logger.warning("[image] 생성 실패: %s: %s", type(e).__name__, msg[:300])
            return _fmt_err(e)
        _count(self.user_id)

        slug = object_storage.safe_slug(filename or prompt, default="image", limit=40)
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}.png"
        path = f"{IMAGES_DIR}/{name}"
        try:
            await _manager().write_file(await _container(self.user_id, self.sandbox_cid), path, data)
        except Exception as e:  # noqa: BLE001  (workspace 저장에 실패해도 공개 업로드는 계속한다)
            logger.warning("[image] workspace 저장 실패: %s", e)
            path = None
        url = None
        if upload:
            try:
                url = await object_storage.upload_public(data, object_storage.make_key(self.user_id, name, "images"), "image/png")
            except Exception as e:  # noqa: BLE001
                logger.warning("[image] 업로드 실패: %s", e)
                if not path:
                    return f"Error: 이미지는 만들었지만 저장·업로드에 모두 실패했습니다: {type(e).__name__}"
                return f"{_result_text(path, None, prompt)}\nUpload failed ({type(e).__name__}); the image exists only in the workspace. You can retry with upload_to_minio."
        await self._record_usage(resp)
        return _result_text(path, url, prompt)

    async def _record_usage(self, resp) -> None:
        """이미지 모델이 돌려준 토큰 사용량을 기록한다 (없으면 생략)."""
        usage = getattr(resp, "usage", None)
        inp, out = getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0
        if not (self.conversation_id and (inp or out)):
            return
        from app.services.token_usage_service import TokenUsageService

        task = asyncio.create_task(TokenUsageService.record_usage_detached(
            user_id=self.user_id, conversation_id=self.conversation_id, llm_provider="openai",
            model_name=settings.OPENAI_IMAGE_MODEL, input_tokens=inp, output_tokens=out, agent_name="generate_image",
        ))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


_tasks: set = set()


# ── upload_to_minio ──────────────────────────────────────────────────────────
class UploadInput(BaseModel):
    path: str = Field(description="Image file in the workspace (png, jpg, gif, webp), e.g. images/logo.png")


class UploadToMinioTool(_AsyncTool):
    name: str = "upload_to_minio"
    description: str = (
        "Upload ONE image file from the workspace to the public MinIO bucket and return its public URL "
        "(anyone with the URL can view it, so only upload images the user wants to share). "
        "Accepts png, jpg, gif, webp up to the size limit. generate_image already uploads by default; "
        "use this for images created by code or for retrying a failed upload."
    )
    args_schema: type[BaseModel] = UploadInput

    async def _arun(self, path: str) -> str:
        if not object_storage.enabled():
            return "Error: 공개 업로드(MinIO)가 설정되어 있지 않습니다 (MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY)"
        try:
            full = resolve_path(path)
            limit = settings.PUBLIC_UPLOAD_MAX_MB * 1024 * 1024
            data, _ = await _manager().read_file(await _container(self.user_id, self.sandbox_cid), full, limit)
            fmt = _image_format(data)  # 확장자가 아니라 실제 내용으로 판별한다 (svg·html 등 스크립트가 들어갈 수 있는 형식은 거부)
            if not fmt:
                return "Error: 이미지(png, jpg, gif, webp)만 공개 업로드할 수 있습니다"
            base = re.sub(r"\.[A-Za-z0-9]+$", "", full.rsplit("/", 1)[-1])
            url = await object_storage.upload_public(
                data, object_storage.make_key(self.user_id, f"{base}.{EXT[fmt]}", "images"), MIME[fmt]
            )
            return _result_text(full, url, base)
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)

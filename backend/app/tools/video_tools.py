"""동영상 생성(generate_video) 도구. 이미지 생성(generate_image)과 같은 방식으로 동작한다.

Gemini Omni 로 영상을 만들어 sandbox /workspace/videos/ 에 저장하고, 기본으로 공개 MinIO 버킷에 올려 공개 URL 을 돌려준다.
(업로드만 따로 하려면 upload_to_minio 가 mp4 도 받는다.)
"""
import asyncio
import logging
import time
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import settings
from app.services import object_storage
from app.services.video_gen import (
    ASPECT_RATIOS, MAX_REFERENCE_IMAGES, RESOLUTIONS, VideoGenerationError, clamp_duration, generate_video, video_api_key,
)
from app.tools.image_tools import _image_format, MIME as IMAGE_MIME
from app.tools.workspace_tools import WORKSPACE, _AsyncTool, _container, _fmt_err, _manager, resolve_path

logger = logging.getLogger(__name__)

VIDEOS_DIR = f"{WORKSPACE}/videos"
MAX_REFERENCE_BYTES = 8 * 1024 * 1024

# (user_id, 날짜) → 오늘 생성 횟수. 프로세스 메모리라 서버를 다시 시작하면 초기화된다.
_daily: dict[tuple[str, date], int] = {}


def _limit_reached(user_id: str) -> bool:
    limit = settings.VIDEO_DAILY_LIMIT
    return bool(limit) and _daily.get((user_id, date.today()), 0) >= limit


def _count(user_id: str) -> None:
    today = date.today()
    for k in [k for k in _daily if k[1] != today]:
        del _daily[k]
    _daily[(user_id, today)] = _daily.get((user_id, today), 0) + 1


class GenerateVideoInput(BaseModel):
    prompt: str = Field(description="Detailed description of the video: subject, action, camera movement, style, mood, setting, any spoken line or sound. Any language")
    seconds: Optional[int] = Field(default=None, description="Length in seconds. One of 4, 6, 8, 10 (nearest is used). Default 6")
    aspect_ratio: Optional[Literal["16:9", "9:16"]] = Field(default=None, description="16:9 (landscape, default) or 9:16 (vertical short-form)")
    resolution: Optional[Literal["360p", "720p", "1080p", "4k"]] = Field(
        default=None, description="Resolution. 360p (default) is a cheap draft; higher costs much more. Use higher only when the user asks"
    )
    reference_images: Optional[list[str]] = Field(
        default=None, description=f"Up to {MAX_REFERENCE_IMAGES} workspace image paths (png/jpg/webp) to use as references for subjects/composition. Optional"
    )
    filename: Optional[str] = Field(default=None, description="Short file name without extension (letters, digits, - _). Optional")
    upload: bool = Field(default=True, description="Upload to the public MinIO bucket and return a public URL (default true)")


class GenerateVideoTool(_AsyncTool):
    name: str = "generate_video"
    description: str = (
        "Generate a NEW short video clip (4-10 seconds, with sound) from a text description, optionally guided by reference images "
        "(storyboards, product shots). Saves the mp4 in /workspace/videos/ and, by default, uploads it to MinIO and returns a public URL. "
        "In your final answer give the user the returned markdown link `[영상 보기](url)`. "
        "It is slow (1-10 minutes) and costly, so generate only what the user asked for (usually one clip), default to 360p and a short length, "
        "and do not call it again just to retry unless it failed. Do not use it to edit an existing video."
    )
    args_schema: type[BaseModel] = GenerateVideoInput
    conversation_id: str = ""

    async def _arun(self, prompt: str, seconds: Optional[int] = None, aspect_ratio: Optional[str] = None,
                    resolution: Optional[str] = None, reference_images: Optional[list[str]] = None,
                    filename: Optional[str] = None, upload: bool = True) -> str:
        if not settings.VIDEO_GENERATION_ENABLED or not video_api_key():
            return "Error: 동영상 생성이 설정되어 있지 않습니다 (VIDEO_GENERATION_ENABLED, VIDEO_API_KEY 또는 GOOGLE_API_KEY)"
        if upload and not object_storage.enabled():
            return "Error: 공개 업로드(MinIO)가 설정되어 있지 않습니다. upload=false 로 workspace 에만 저장하거나 관리자에게 MinIO 설정을 요청하세요"
        if not prompt.strip():
            return "Error: prompt 가 비어 있습니다"
        if _limit_reached(self.user_id):
            return f"Error: 오늘의 동영상 생성 한도({settings.VIDEO_DAILY_LIMIT}개)에 도달했습니다. 내일 다시 시도해 주세요"
        seconds = clamp_duration(seconds or settings.VIDEO_DEFAULT_SECONDS)
        ratio = aspect_ratio if aspect_ratio in ASPECT_RATIOS else settings.VIDEO_ASPECT_RATIO
        res = resolution if resolution in RESOLUTIONS else settings.VIDEO_RESOLUTION

        refs, ref_err = await self._load_references(reference_images or [])
        if ref_err:
            return ref_err
        try:
            result = await generate_video(prompt[:4000], seconds, ratio, res, refs)
        except VideoGenerationError as e:
            logger.warning("[video] 생성 실패: %s", e)
            return f"Error: {e}"
        except Exception as e:  # noqa: BLE001
            logger.warning("[video] 생성 실패: %s: %s", type(e).__name__, str(e)[:300])
            return _fmt_err(e)
        _count(self.user_id)

        slug = object_storage.safe_slug(filename or prompt, default="video", limit=40)
        name = f"{time.strftime('%Y%m%d-%H%M%S')}-{slug}.mp4"
        path = f"{VIDEOS_DIR}/{name}"
        try:
            await _manager().write_file(await _container(self.user_id, self.sandbox_cid), path, result.content)
        except Exception as e:  # noqa: BLE001  (workspace 저장에 실패해도 공개 업로드는 계속한다)
            logger.warning("[video] workspace 저장 실패: %s", e)
            path = None
        url = None
        if upload:
            try:
                url = await object_storage.upload_public(result.content, object_storage.make_key(self.user_id, name, "videos"), "video/mp4")
            except Exception as e:  # noqa: BLE001
                logger.warning("[video] 업로드 실패: %s", e)
                if not path:
                    return f"Error: 영상은 만들었지만 저장·업로드에 모두 실패했습니다: {type(e).__name__}"
                return (f"{_result_text(path, None, result)}\nUpload failed ({type(e).__name__}); the video exists only in the workspace. "
                        "You can retry with upload_to_minio.")
        return _result_text(path, url, result)

    async def _load_references(self, paths: list[str]):
        """workspace 의 참조 이미지를 읽는다. (이미지 목록, 오류 문구)"""
        refs: list[tuple[bytes, str]] = []
        for p in paths[:MAX_REFERENCE_IMAGES]:
            try:
                data, _ = await _manager().read_file(await _container(self.user_id, self.sandbox_cid), resolve_path(p), MAX_REFERENCE_BYTES)
            except Exception as e:  # noqa: BLE001
                return [], f"Error: 참조 이미지를 읽지 못했습니다 ({p}): {type(e).__name__}"
            fmt = _image_format(data)
            if fmt not in ("png", "jpeg", "webp"):
                return [], f"Error: 참조 이미지는 png, jpg, webp 만 쓸 수 있습니다: {p}"
            refs.append((data, IMAGE_MIME[fmt]))
        return refs, None


def _result_text(path: Optional[str], url: Optional[str], result) -> str:
    lines = [f"Video generated: {result.seconds}s, {result.meta.get('resolution')}, {result.meta.get('aspect_ratio')}, model {result.model}"]
    if path:
        lines.append(f"Saved in workspace: {path}")
    if url:
        lines.append(f"Public URL: {url}")
        lines.append(f"Give the user this link in your answer (it plays inline in the chat): [영상 보기]({url})")
    return "\n".join(lines)

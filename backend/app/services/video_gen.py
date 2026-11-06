"""동영상 생성 (Google Gemini Omni, Interactions API). 구현은 ai_marketing_dashboard_v2 의 video_gen/omni.py 를 참고했다.

SDK 대신 REST 를 httpx 로 직접 부른다: Interactions API 의 현행 스키마는 google-genai >= 2.0 만 지원하는데,
이 프로젝트의 langchain-google-genai 가 google-genai < 2 를 요구해 SDK 를 올릴 수 없기 때문이다 (SDK 2.x 가 보내는 요청 형식을 그대로 따른다).
- ``POST /v1beta/interactions`` (background=false) 는 영상이 만들어질 때까지 응답이 오지 않는 동기 호출이다.
- 길이를 정하는 파라미터가 없어 프롬프트에 길이를 적어 유도하고, 실제 길이는 결과 mp4 에서 읽는다.
- 해상도·비율은 ``response_format`` 에 담는다. 오디오는 기본으로 생성된다 (VIDEO_STRIP_AUDIO 로 ffmpeg 후처리 제거).
- 결과는 base64 인라인(``output_video.data``)이 기본이고, 크면 파일 URI 로 와서 둘 다 받는다.
"""
import asyncio
import base64
import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_DURATIONS = (4, 6, 8, 10)
MAX_REFERENCE_IMAGES = 3
ASPECT_RATIOS = ("16:9", "9:16")
RESOLUTIONS = ("360p", "720p", "1080p", "4k")

# 이 모델에는 negative prompt 파라미터가 없어 프롬프트 끝에 "피할 것" 문장으로 붙인다.
_AVOID = "garbled text, distorted letters, unreadable text, misspelled words, watermark, blank background"
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_NOT_ABOUT_REFS = frozenset({401, 403, 404, 429})


class VideoGenerationError(RuntimeError):
    """생성 실패. 메시지는 사용자에게 그대로 보일 수 있다."""


@dataclass(frozen=True)
class VideoResult:
    content: bytes
    model: str
    seconds: int  # 요청값이 아니라 실제 생성된 길이
    meta: dict = field(default_factory=dict)


def clamp_duration(seconds: int, supported: Sequence[int] = SUPPORTED_DURATIONS) -> int:
    """지원하는 길이 중 가장 가까운 값."""
    return min(supported, key=lambda s: (abs(s - seconds), s))


def build_prompt(prompt: str, seconds: int, ref_count: int = 0) -> str:
    parts = []
    if ref_count:
        tags = ", ".join(f"<IMAGE_REF_{i}>" for i in range(ref_count))
        parts.append(f"Use the attached images ({tags}) as references for the subjects, products and composition.")
    parts.append((prompt or "").strip())
    parts.append(f"Total length: about {seconds} seconds.")
    parts.append(f"Avoid: {_AVOID}.")
    return "\n\n".join(p for p in parts if p)


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        import shutil

        return shutil.which("ffmpeg")


def probe_seconds(content: bytes):
    """mp4 의 실제 재생 길이(초). ffmpeg 가 없거나 읽지 못하면 None."""
    exe = _ffmpeg_exe()
    if not exe:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = f"{tmp}/in.mp4"
            with open(src, "wb") as f:
                f.write(content)
            # `ffmpeg -i` 는 출력이 없어 non-zero 로 끝나지만 stderr 에 Duration 을 찍는다
            out = subprocess.run([exe, "-hide_banner", "-i", src], capture_output=True, text=True, timeout=30).stderr
    except Exception as e:  # noqa: BLE001
        logger.debug("영상 길이 확인 실패: %s", e)
        return None
    m = _DURATION_RE.search(out)
    if not m:
        return None
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def strip_audio(content: bytes) -> bytes:
    """오디오 트랙 제거. 실패하면 원본을 그대로 돌려준다 (소리가 섞여 있어도 영상이 없는 것보다 낫다)."""
    exe = _ffmpeg_exe()
    if not exe:
        logger.warning("ffmpeg 를 찾지 못해 오디오를 제거하지 못했습니다 — 원본을 사용합니다.")
        return content
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = f"{tmp}/in.mp4", f"{tmp}/out.mp4"
        with open(src, "wb") as f:
            f.write(content)
        try:
            subprocess.run([exe, "-y", "-loglevel", "error", "-i", src, "-an", "-c:v", "copy", dst], check=True, timeout=120)
            with open(dst, "rb") as f:
                return f.read() or content
        except Exception as e:  # noqa: BLE001
            logger.warning("오디오 제거 실패 — 원본을 사용합니다: %s", e)
            return content


API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def video_api_key() -> str:
    """영상 생성에 쓰는 Gemini API 키 (VIDEO_API_KEY, 없으면 GOOGLE_API_KEY)."""
    return settings.VIDEO_API_KEY or settings.GOOGLE_API_KEY


class VideoApiError(Exception):
    """Gemini API HTTP 오류 (status_code 로 재시도 여부를 판단한다)."""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


def _error_message(resp) -> str:
    try:
        return str(resp.json().get("error", {}).get("message") or resp.text)[:300]
    except Exception:  # noqa: BLE001
        return resp.text[:300]


def find_video(interaction: dict):
    """응답의 steps 에서 마지막 model_output 안의 마지막 video 항목 (SDK 의 output_video 와 같은 규칙)."""
    for step in reversed(interaction.get("steps") or []):
        if step.get("type") == "user_input":
            break
        if step.get("type") != "model_output" or not isinstance(step.get("content"), list):
            continue
        for item in reversed(step["content"]):
            if isinstance(item, dict) and item.get("type") == "video":
                return item
    return None


async def _video_bytes(client, interaction: dict) -> bytes:
    video = find_video(interaction)
    if video is None:
        raise VideoGenerationError("영상 모델이 영상을 돌려주지 않았습니다 (안전 정책에 걸렸거나 요청이 거절됐을 수 있습니다).")
    if video.get("data"):
        try:
            return base64.b64decode(video["data"])
        except Exception as e:  # noqa: BLE001
            raise VideoGenerationError(f"영상 디코딩 실패: {type(e).__name__}") from e
    uri = video.get("uri")
    if uri:  # 큰 결과는 파일 URI 로 온다
        try:
            resp = await client.get(uri, headers={"x-goog-api-key": video_api_key()}, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except Exception as e:  # noqa: BLE001
            raise VideoGenerationError(f"결과 영상 다운로드 실패: {type(e).__name__}") from e
    raise VideoGenerationError("영상 모델 응답에 영상 데이터가 없습니다.")


def _refs_might_be_the_cause(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in _NOT_ABOUT_REFS:
        return False
    if any(h in str(exc).lower() for h in ("image", "reference", "mime")):
        return True
    return code in (None, 400)


async def generate_video(
    prompt: str,
    seconds: int,
    aspect_ratio: str,
    resolution: str,
    reference_images: Sequence[tuple[bytes, str]] = (),
    timeout=None,
) -> VideoResult:
    """영상을 만든다 (수 분 걸릴 수 있다). 실패하면 VideoGenerationError."""
    import httpx

    if not video_api_key():
        raise VideoGenerationError("Gemini(Google) API 키가 설정되지 않았습니다 (VIDEO_API_KEY 또는 GOOGLE_API_KEY).")
    timeout = timeout or settings.VIDEO_TIMEOUT_SECONDS
    actual = clamp_duration(seconds)
    refs = list(reference_images)[:MAX_REFERENCE_IMAGES]
    model = settings.VIDEO_MODEL

    async def request(client, with_refs: bool) -> dict:
        use = refs if with_refs else []
        parts = [{"type": "image", "data": base64.b64encode(b).decode("ascii"), "mime_type": m} for b, m in use]
        parts.append({"type": "text", "text": build_prompt(prompt, actual, len(use))})  # 이미지 파트가 먼저, 텍스트가 마지막
        body = {
            "model": model,
            "input": [{"type": "user_input", "content": parts}],
            "response_format": {"type": "video", "resolution": resolution, "aspect_ratio": aspect_ratio},
            "background": False, "store": False, "stream": False,
        }
        resp = await client.post(f"{API_BASE}/interactions", json=body,
                                 headers={"x-goog-api-key": video_api_key(), "content-type": "application/json"})
        if resp.status_code >= 400:
            raise VideoApiError(resp.status_code, _error_message(resp))
        return resp.json()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=15)) as client:
            used = len(refs)
            try:
                interaction = await request(client, True)
            except (VideoApiError, httpx.HTTPError) as e:
                # 첨부 때문에 거절된 것으로 보이면 첨부 없이 한 번 더 시도한다. 키·권한·쿼터 문제면 재시도하지 않는다.
                if not refs or isinstance(e, httpx.HTTPError) or not _refs_might_be_the_cause(e):
                    raise VideoGenerationError(f"영상 생성 요청 실패: {_describe(e)}") from e
                logger.warning("참조 이미지가 거절 원인일 수 있어 첨부 없이 재시도: %s", str(e)[:200])
                used = 0
                try:
                    interaction = await request(client, False)
                except (VideoApiError, httpx.HTTPError) as e2:
                    raise VideoGenerationError(f"영상 생성 요청 실패: {_describe(e2)}") from e2
            if str(interaction.get("status", "")).lower() in ("failed", "cancelled", "incomplete"):
                raise VideoGenerationError(f"영상 생성이 완료되지 않았습니다 (status={interaction.get('status')}).")
            content = await _video_bytes(client, interaction)
    except httpx.TimeoutException as e:
        raise VideoGenerationError(f"영상 생성이 {timeout}초 안에 끝나지 않았습니다. 잠시 후 다시 시도해 주세요.") from e
    if not content:
        raise VideoGenerationError("영상 모델이 빈 영상을 돌려주었습니다.")
    if settings.VIDEO_STRIP_AUDIO:
        content = await asyncio.to_thread(strip_audio, content)
    measured = await asyncio.to_thread(probe_seconds, content)
    final = max(1, round(measured)) if measured else actual  # 기록하는 길이는 요청값이 아니라 실제 길이를 따른다
    logger.info("영상 생성 완료 model=%s %s %s seconds=%d(요청 %d) bytes=%d", model, resolution, aspect_ratio, final, actual, len(content))
    return VideoResult(
        content=content, model=model, seconds=final,
        meta={"resolution": resolution, "aspect_ratio": aspect_ratio, "reference_images": used, "requested_seconds": actual,
              "audio": not settings.VIDEO_STRIP_AUDIO, "usage": interaction.get("usage")},
    )


def _describe(e: Exception) -> str:
    if isinstance(e, VideoApiError):
        return str(e)
    return f"[{type(e).__name__}] {str(e)[:200]}"

"""공개 읽기 MinIO 버킷에 파일을 올리고 공개 URL 을 돌려준다 (이미지 생성 결과·공개 업로드 도구가 쓴다).

버킷(MINIO_PUBLIC_BUCKET)은 처음 쓸 때 만들고 익명 읽기(s3:GetObject) 정책을 건다. 객체 키에는 추측하기 어려운 uuid 가
들어가지만 URL 을 아는 누구나 읽을 수 있으므로 비밀 파일을 올리면 안 된다.
sandbox 백업 버킷(MINIO_BUCKET)과는 별개이며 같은 MinIO 서버·인증 정보를 쓴다.
"""
import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_bucket_ready = False


def enabled() -> bool:
    return bool(settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY)


def _get_client():
    global _client
    if _client is None:
        from minio import Minio

        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def _ensure_public_bucket(client) -> None:
    """버킷이 없으면 만들고, 익명 읽기 정책을 건다 (프로세스당 한 번)."""
    global _bucket_ready
    if _bucket_ready:
        return
    bucket = settings.MINIO_PUBLIC_BUCKET
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow", "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"], "Resource": [f"arn:aws:s3:::{bucket}/*"],
        }],
    }
    client.set_bucket_policy(bucket, json.dumps(policy))
    _bucket_ready = True


def public_base_url() -> str:
    base = settings.MINIO_PUBLIC_URL.strip().rstrip("/")
    return base or f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}"


def public_url(key: str) -> str:
    return f"{public_base_url()}/{settings.MINIO_PUBLIC_BUCKET}/{quote(key)}"


def safe_slug(name: str, default: str = "file", limit: int = 60) -> str:
    """파일명/설명을 URL 에 안전한 짧은 이름으로 (한글·특수문자는 _ 로)."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", name or "").strip("._-")
    return s[:limit] or default


def make_key(user_id: str, filename: str, prefix: str = "files") -> str:
    """{prefix}/{사용자 앞 8자}/{YYYYMMDD}/{uuid8}-{이름}"""
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}/{user_id[:8]}/{day}/{uuid.uuid4().hex[:8]}-{safe_slug(filename)}"


def _upload_sync(data: bytes, key: str, content_type: str) -> str:
    import io

    client = _get_client()
    _ensure_public_bucket(client)
    client.put_object(settings.MINIO_PUBLIC_BUCKET, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return public_url(key)


async def upload_public(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """바이트를 공개 버킷에 올리고 공개 URL 을 돌려준다. MinIO 가 설정되지 않았으면 RuntimeError."""
    if not enabled():
        raise RuntimeError("MinIO 가 설정되지 않았습니다 (MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY)")
    return await asyncio.to_thread(_upload_sync, data, key, content_type)


def delete_public(key: str) -> None:
    _get_client().remove_object(settings.MINIO_PUBLIC_BUCKET, key)

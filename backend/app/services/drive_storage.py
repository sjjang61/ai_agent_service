"""Drive 파일 본문 저장소 (MinIO 비공개 버킷).

버킷(MINIO_DRIVE_BUCKET)은 처음 쓸 때 만들고 **익명 정책을 걸지 않는다**. 공개 버킷(object_storage.py)과 코드·버킷 모두 분리한다.
객체 키는 불투명한 값(drive/{user_id}/{node_id})이라 파일 이름·경로가 키에 들어가지 않는다.
MinIO 클라이언트는 동기라서 asyncio.to_thread 로 부른다. 테스트에서는 같은 인터페이스의 메모리 구현으로 바꿔 쓴다.
"""
import asyncio
import logging
from typing import BinaryIO, Iterator, Optional

from app.config import settings

logger = logging.getLogger(__name__)

CHUNK = 64 * 1024


def enabled() -> bool:
    return bool(settings.DRIVE_ENABLED and settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY)


def make_key(user_id: str, node_id: str) -> str:
    return f"drive/{user_id}/{node_id}"


class DriveStorage:
    def __init__(self):
        self._client = None
        self._bucket_ready = False

    def _get_client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(settings.MINIO_ENDPOINT, access_key=settings.MINIO_ACCESS_KEY, secret_key=settings.MINIO_SECRET_KEY, secure=settings.MINIO_SECURE)
        return self._client

    def _ensure_bucket(self, client) -> None:
        if self._bucket_ready:
            return
        if not client.bucket_exists(settings.MINIO_DRIVE_BUCKET):
            client.make_bucket(settings.MINIO_DRIVE_BUCKET)
        self._bucket_ready = True

    # ── 동기 구현 ────────────────────────────────────────────
    def _put_sync(self, key: str, fileobj: BinaryIO, length: int, content_type: str) -> None:
        client = self._get_client()
        self._ensure_bucket(client)
        client.put_object(settings.MINIO_DRIVE_BUCKET, key, fileobj, length=length, content_type=content_type or "application/octet-stream")

    def _open_sync(self, key: str):
        return self._get_client().get_object(settings.MINIO_DRIVE_BUCKET, key)

    def _remove_sync(self, key: str) -> None:
        self._get_client().remove_object(settings.MINIO_DRIVE_BUCKET, key)

    def _list_sync(self, prefix: str) -> list[str]:
        client = self._get_client()
        self._ensure_bucket(client)
        return [o.object_name for o in client.list_objects(settings.MINIO_DRIVE_BUCKET, prefix=prefix, recursive=True)]

    # ── 비동기 인터페이스 ────────────────────────────────────
    async def put(self, key: str, fileobj: BinaryIO, length: int, content_type: str = "application/octet-stream") -> None:
        await asyncio.to_thread(self._put_sync, key, fileobj, length, content_type)

    async def remove(self, key: str) -> None:
        await asyncio.to_thread(self._remove_sync, key)

    async def list_keys(self, prefix: str) -> list[str]:
        return await asyncio.to_thread(self._list_sync, prefix)

    async def stream(self, key: str) -> "AsyncIterator[bytes]":  # noqa: F821
        """객체를 CHUNK 단위로 흘려보낸다. 응답이 끝나거나 끊기면 연결을 닫는다."""
        resp = await asyncio.to_thread(self._open_sync, key)
        try:
            it: Iterator[bytes] = resp.stream(CHUNK)
            while True:
                chunk = await asyncio.to_thread(next, it, None)
                if chunk is None:
                    break
                yield chunk
        finally:
            resp.close()
            resp.release_conn()


storage = DriveStorage()

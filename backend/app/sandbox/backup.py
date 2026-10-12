"""Sandbox /workspace 를 MinIO 에 세션 id 폴더로 백업/복구한다.

객체 경로: {bucket}/{session_id}/workspace.tar.gz  (항상 최신 1개만 유지)
"""
import asyncio
import logging
import os
import tempfile
from typing import Optional

from app.config import settings
from app.sandbox.manager import SandboxManager

logger = logging.getLogger(__name__)

OBJECT_NAME = "workspace.tar.gz"


class SandboxBackup:
    def __init__(self, manager: SandboxManager):
        self._manager = manager
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(
            settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY and settings.MINIO_SECRET_KEY
        )

    def _get_client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
        return self._client

    @staticmethod
    def object_key(session_id: str) -> str:
        return f"{session_id}/{OBJECT_NAME}"

    # ── MinIO (동기 SDK → thread) ────────────────────────────────────────────
    def _upload(self, session_id: str, path: str):
        client = self._get_client()
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
        client.fput_object(
            settings.MINIO_BUCKET, self.object_key(session_id), path,
            content_type="application/gzip",
        )

    def _download(self, session_id: str, path: str) -> bool:
        from minio.error import S3Error

        try:
            self._get_client().fget_object(settings.MINIO_BUCKET, self.object_key(session_id), path)
            return True
        except S3Error as e:
            if e.code in ("NoSuchKey", "NoSuchBucket", "NoSuchObject"):
                return False
            raise

    def _exists(self, session_id: str) -> bool:
        from minio.error import S3Error

        try:
            self._get_client().stat_object(settings.MINIO_BUCKET, self.object_key(session_id))
            return True
        except S3Error as e:
            if e.code in ("NoSuchKey", "NoSuchBucket", "NoSuchObject"):
                return False
            raise

    # ── public ───────────────────────────────────────────────────────────────
    async def exists(self, session_id: str) -> bool:
        return self.enabled and await asyncio.to_thread(self._exists, session_id)

    async def backup(self, session_id: str, container_id: str) -> int:
        """컨테이너의 /workspace 를 MinIO {session_id}/ 에 저장. 실패하면 예외."""
        fd, tmp = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)
        try:
            size = await self._manager.export_workspace(
                container_id, tmp, settings.SANDBOX_BACKUP_MAX_MB * 1024 * 1024
            )
            await asyncio.to_thread(self._upload, session_id, tmp)
            logger.info("[sandbox] backup 완료 session=%s size=%dB", session_id, size)
            return size
        finally:
            _unlink(tmp)

    async def restore(self, session_id: str, container_id: str) -> bool:
        """MinIO {session_id}/ 의 백업을 컨테이너 /workspace 로 복구. 백업이 없으면 False."""
        if not self.enabled:
            return False
        fd, tmp = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)
        try:
            if not await asyncio.to_thread(self._download, session_id, tmp):
                return False
            await self._manager.import_workspace(container_id, tmp)
            logger.info("[sandbox] restore 완료 session=%s", session_id)
            return True
        finally:
            _unlink(tmp)


def _unlink(path: Optional[str]):
    try:
        if path:
            os.unlink(path)
    except OSError:
        pass

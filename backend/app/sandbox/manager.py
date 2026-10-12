import asyncio
import gzip
import io
import os
import shlex
import tarfile
from pathlib import Path

from app.config import settings


class SandboxManager:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    async def create_sandbox(self, user_id: str) -> str:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _create():
            return client.containers.run(
                image=settings.SANDBOX_IMAGE,
                name=f"sandbox-{user_id[:8]}-{id(object()) % 100000}",
                detach=True,
                remove=False,
                mem_limit=settings.SANDBOX_MEMORY_LIMIT,
                cpu_quota=100000,
                environment={
                    "USER_ID": user_id,
                    "HOME": "/workspace",
                },
                working_dir="/workspace",
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
            )

        container = await loop.run_in_executor(None, _create)
        return container.id

    async def exec_command(
        self, container_id: str, command: str, timeout: int = 30
    ) -> tuple[int, str, str]:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _exec():
            container = client.containers.get(container_id)
            result = container.exec_run(
                cmd=["bash", "-c", command],
                stdout=True,
                stderr=True,
                demux=True,
            )
            exit_code = result.exit_code or 0
            stdout = (result.output[0] or b"").decode("utf-8", errors="replace")
            stderr = (result.output[1] or b"").decode("utf-8", errors="replace")
            return exit_code, stdout, stderr

        return await asyncio.wait_for(
            loop.run_in_executor(None, _exec), timeout=timeout
        )

    async def put_directory(
        self, container_id: str, local_dir: Path, dest_parent: str, name: str
    ) -> str:
        """호스트 디렉터리를 컨테이너의 {dest_parent}/{name} 으로 복사한다 (기존 내용은 교체).

        put_archive(tar) 를 사용하므로 바이너리 파일도 안전하게 전달되고,
        sandbox 유저(uid 1000)가 읽고 쓸 수 있도록 소유자를 맞춘다.
        """
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _chown(ti: tarfile.TarInfo) -> tarfile.TarInfo:
            ti.uid = ti.gid = 1000
            ti.uname = ti.gname = ""
            return ti

        def _put() -> str:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                tar.add(str(local_dir), arcname=name, filter=_chown)
            container = client.containers.get(container_id)
            dest = f"{dest_parent}/{name}"
            container.exec_run(["bash", "-c", f"rm -rf {shlex.quote(dest)} && mkdir -p {shlex.quote(dest_parent)}"])
            if not container.put_archive(dest_parent, buf.getvalue()):
                raise RuntimeError(f"put_archive failed: {dest}")
            return dest

        return await loop.run_in_executor(None, _put)

    async def is_running(self, container_id: str) -> bool:
        """컨테이너가 실제로 존재하고 실행 중인지 확인 (DB 상태와의 불일치 감지용)."""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _check() -> bool:
            try:
                container = client.containers.get(container_id)
                return container.status == "running"
            except Exception:
                return False

        return await loop.run_in_executor(None, _check)

    async def export_workspace(self, container_id: str, out_path: str, max_bytes: int) -> int:
        """/workspace 전체를 tar.gz 로 out_path 에 저장한다. 저장된 파일 크기를 반환."""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _export() -> int:
            container = client.containers.get(container_id)
            stream, _ = container.get_archive("/workspace")
            total = 0
            with gzip.open(out_path, "wb", compresslevel=3) as gz:
                for chunk in stream:
                    total += len(chunk)
                    if total > max_bytes:
                        raise RuntimeError(
                            f"workspace 가 백업 제한({max_bytes // (1024 * 1024)}MB)을 초과했습니다"
                        )
                    gz.write(chunk)
            return os.path.getsize(out_path)

        return await loop.run_in_executor(None, _export)

    async def export_path(self, container_id: str, path: str, out_path: str, max_bytes: int) -> int:
        """컨테이너의 파일/디렉터리를 (압축 없는) tar 로 out_path 에 저장한다."""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _export() -> int:
            container = client.containers.get(container_id)
            stream, _ = container.get_archive(path)
            total = 0
            with open(out_path, "wb") as f:
                for chunk in stream:
                    total += len(chunk)
                    if total > max_bytes:
                        raise RuntimeError(f"{path} 가 크기 제한({max_bytes // (1024 * 1024)}MB)을 초과했습니다")
                    f.write(chunk)
            return total

        return await loop.run_in_executor(None, _export)

    async def import_workspace(self, container_id: str, archive_path: str):
        """export_workspace 로 만든 tar.gz 를 컨테이너의 /workspace 로 복원한다."""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _import():
            container = client.containers.get(container_id)
            with gzip.open(archive_path, "rb") as f:
                # 아카이브의 최상위 디렉터리가 workspace/ 이므로 '/' 에 푼다
                if not container.put_archive("/", f):
                    raise RuntimeError("put_archive failed")

        await loop.run_in_executor(None, _import)

    async def remove_path(self, container_id: str, path: str):
        await self.exec_command(container_id, f"rm -rf {shlex.quote(path)}")

    async def destroy_sandbox(self, container_id: str):
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _destroy():
            try:
                container = client.containers.get(container_id)
                container.stop(timeout=5)
                container.remove()
            except Exception:
                pass

        await loop.run_in_executor(None, _destroy)

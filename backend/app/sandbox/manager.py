import asyncio
import gzip
import io
import json
import os
import posixpath
import shlex
import socket
import struct
import tarfile
import threading
import time
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

    def _ensure_network(self) -> str | None:
        """sandbox 전용 네트워크. 컨테이너끼리의 통신(icc)을 막아 사용자·대화방 간 접근을 차단한다 (외부 인터넷은 그대로).
        만들 수 없으면 None (기본 bridge 로 폴백, 경고)."""
        name = settings.SANDBOX_NETWORK
        if not name:
            return None
        client = self._get_client()
        try:
            client.networks.get(name)
            return name
        except Exception:
            pass
        try:
            client.networks.create(name, driver="bridge", options={"com.docker.network.bridge.enable_icc": "false"})
            return name
        except Exception:
            import logging

            logging.getLogger(__name__).warning("[sandbox] 전용 네트워크 %s 를 만들지 못했습니다 — 기본 bridge 사용", name, exc_info=True)
            return None

    async def create_sandbox(self, user_id: str, conversation_id: str | None = None) -> str:
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _create():
            import uuid as _uuid

            network = self._ensure_network()
            scope = (conversation_id or "shared")[:8]
            return client.containers.run(
                image=settings.SANDBOX_IMAGE,
                name=f"sandbox-{user_id[:8]}-{scope}-{_uuid.uuid4().hex[:6]}",
                labels={"agent-sandbox": "1", "agent-sandbox-user": user_id, "agent-sandbox-conversation": conversation_id or ""},
                **({"network": network} if network else {}),
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

    async def read_file(self, container_id: str, path: str, max_bytes: int) -> tuple[bytes, int]:
        """컨테이너 파일 하나를 읽는다. (내용, 파일 mode) 반환.

        없으면 FileNotFoundError, 디렉터리면 IsADirectoryError, 제한 초과면 ValueError.
        """
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _read() -> tuple[bytes, int]:
            from docker.errors import NotFound

            container = client.containers.get(container_id)
            try:
                stream, _ = container.get_archive(path)
            except NotFound:
                raise FileNotFoundError(path)
            buf, total = io.BytesIO(), 0
            for chunk in stream:
                total += len(chunk)
                if total > max_bytes + 1024 * 1024:  # tar 헤더/패딩 여유
                    raise ValueError(f"파일이 너무 큽니다 (최대 {max_bytes // (1024 * 1024)}MB)")
                buf.write(chunk)
            buf.seek(0)
            with tarfile.open(fileobj=buf) as tar:
                members = tar.getmembers()
                if not members or members[0].isdir():
                    raise IsADirectoryError(path)
                m = members[0]
                if m.size > max_bytes:
                    raise ValueError(f"파일이 너무 큽니다 (최대 {max_bytes // (1024 * 1024)}MB)")
                return tar.extractfile(m).read(), m.mode

        return await loop.run_in_executor(None, _read)

    async def write_file(self, container_id: str, path: str, data: bytes, mode: int = 0o644):
        """컨테이너에 파일을 쓴다 (상위 디렉터리 자동 생성, 소유자 uid 1000)."""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        def _write():
            container = client.containers.get(container_id)
            parent, name = posixpath.split(path)
            res = container.exec_run(["mkdir", "-p", parent])
            if res.exit_code != 0:
                raise RuntimeError((res.output or b"").decode("utf-8", errors="replace").strip() or f"mkdir failed: {parent}")
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                ti = tarfile.TarInfo(name)
                ti.size, ti.mode, ti.uid, ti.gid = len(data), mode, 1000, 1000
                ti.mtime = int(time.time())
                tar.addfile(ti, io.BytesIO(data))
            if not container.put_archive(parent, buf.getvalue()):
                raise RuntimeError(f"파일 쓰기 실패: {path}")

        await loop.run_in_executor(None, _write)

    async def exec_with_rpc(
        self,
        container_id: str,
        cmd: list[str],
        rpc_handler,
        timeout: int,
        rpc_prefix: str = "@@MCP_RPC@@",
        max_rpc: int = 200,
        max_output_bytes: int = 200_000,
    ) -> tuple[int, str, str, int]:
        """컨테이너에서 cmd 를 실행하면서, stdout 의 `rpc_prefix{json}` 줄을 RPC 요청으로 처리한다.

        요청마다 `await rpc_handler(dict) -> dict` 를 실행하고 그 결과를 한 줄 JSON 으로 프로세스 stdin 에 돌려준다.
        그 외의 stdout/stderr 는 일반 출력으로 수집한다. 반환: (exit_code, stdout, stderr, rpc_count)
        """
        loop = asyncio.get_running_loop()
        client = self._get_client()
        stop = threading.Event()  # 호출이 취소되면 스레드를 멈춘다

        def _run():
            api = client.api
            ex = api.exec_create(container_id, cmd, stdin=True, stdout=True, stderr=True, tty=False)
            sock = api.exec_start(ex["Id"], socket=True, demux=False)
            raw = getattr(sock, "_sock", sock)
            raw.settimeout(1.0)
            deadline = time.monotonic() + timeout
            pending, out_lines, err = b"", [], bytearray()
            out_size, rpc_count, timed_out = 0, 0, False

            def read_exact(n: int):
                buf = bytearray()
                while len(buf) < n:
                    if stop.is_set():
                        raise InterruptedError
                    if time.monotonic() > deadline:
                        raise TimeoutError
                    try:
                        chunk = raw.recv(n - len(buf))
                    except socket.timeout:
                        continue
                    if not chunk:
                        return None
                    buf.extend(chunk)
                return bytes(buf)

            def emit(text: str):
                nonlocal out_size
                if out_size < max_output_bytes:
                    out_lines.append(text)
                    out_size += len(text) + 1

            try:
                while True:
                    header = read_exact(8)
                    if not header:
                        break
                    stream, size = header[0], struct.unpack(">I", header[4:8])[0]
                    data = read_exact(size) if size else b""
                    if data is None:
                        break
                    if stream == 2:  # stderr
                        if len(err) < max_output_bytes:
                            err.extend(data)
                        continue
                    pending += data
                    while b"\n" in pending:
                        line, pending = pending.split(b"\n", 1)
                        text = line.decode("utf-8", errors="replace")
                        if not text.startswith(rpc_prefix):
                            emit(text)
                            continue
                        rpc_count += 1
                        if stop.is_set():
                            raise InterruptedError  # 취소 이후에는 MCP 호출을 더 보내지 않는다
                        if rpc_count > max_rpc:
                            resp = {"error": f"RPC 호출 한도({max_rpc})를 초과했습니다"}
                        else:
                            try:
                                req = json.loads(text[len(rpc_prefix):])
                                resp = asyncio.run_coroutine_threadsafe(rpc_handler(req), loop).result(timeout=120)
                            except Exception as e:  # noqa: BLE001
                                resp = {"error": f"{type(e).__name__}: {e}"}
                        raw.sendall((json.dumps(resp, ensure_ascii=False, default=str) + "\n").encode("utf-8"))
            except TimeoutError:
                timed_out = True
            except InterruptedError:
                pass
            finally:
                try:
                    raw.close()
                except OSError:
                    pass
            if pending:
                emit(pending.decode("utf-8", errors="replace"))
            code = api.exec_inspect(ex["Id"]).get("ExitCode")
            if timed_out or code is None:
                code = 124
            return code, "\n".join(out_lines), err.decode("utf-8", errors="replace"), rpc_count

        try:
            return await loop.run_in_executor(None, _run)
        except asyncio.CancelledError:
            stop.set()
            raise

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

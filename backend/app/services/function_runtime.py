"""Function 실행기: 요청 한 건마다 새 격리 컨테이너를 만들어 패키지를 올려 실행하고 항상 폐기한다.

RuntimeBackend 인터페이스 뒤에 Docker 구현을 둔다. 나중에 별도 러너 호스트·Kubernetes Job 으로 바꿀 때 이 파일만 교체한다.

격리: 읽기 전용 루트 + tmpfs(/tmp, /var/task), cap_drop=ALL, no-new-privileges, uid 1000, 네트워크 none(기본), pids/메모리/CPU 제한,
스왑 금지, 호스트 볼륨·docker.sock 없음. 패키지와 이벤트는 stdin 프로토콜로 넣는다(infra/functions/entry.sh).
결과는 실행마다 새로 만든 토큰이 붙은 마커 줄(__FN_RESULT_<token>__)로 돌려받는다.
"""
import asyncio
import gzip
import io
import json
import logging
import re
import secrets
import tarfile
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.config import settings

logger = logging.getLogger(__name__)

LABEL = "agent-fn-run"
_MB = 1024 * 1024
RUNTIMES = {"python3.12": "FUNCTION_RUNTIME_IMAGE_PYTHON", "bun": "FUNCTION_RUNTIME_IMAGE_BUN"}


def image_for(runtime: str) -> str:
    return getattr(settings, RUNTIMES[runtime])


@dataclass
class RunSpec:
    run_id: str
    runtime: str  # python3.12 | bun
    event: bytes  # JSON 바이트
    unpacked_bytes: int
    package_tar: bytes = b""  # 검증·정규화된 tar (작은 패키지·테스트용)
    package_path: str = ""  # 또는 tar.gz 파일 경로: 압축을 풀며 stdin 으로 흘려 보낸다 (메모리에 올리지 않는다)
    package_size: int = 0  # package_path 의 압축을 푼 tar 길이
    function: str = ""
    version: str = ""
    env: dict = field(default_factory=dict)  # 평문 환경변수 (시크릿 포함)
    secret_values: list = field(default_factory=list)  # 로그에서 가릴 값
    timeout_s: int = 30
    memory_mb: int = 256
    cpu: float = 0.5
    allow_network: bool = False


@dataclass
class RunOutcome:
    status: str  # succeeded | failed | timeout | cancelled
    exit_code: Optional[int] = None
    result: object = None
    error: Optional[dict] = None
    log: str = ""
    log_truncated: bool = False
    cold_start_ms: int = 0  # 컨테이너를 만들고 시작해 패키지를 전달하기까지
    duration_ms: int = 0  # 시작부터 종료까지
    oom: bool = False


class RuntimeBackend(Protocol):
    async def run(self, spec: RunSpec, cancel: asyncio.Event) -> RunOutcome: ...
    async def cleanup_orphans(self) -> int: ...


def make_tar(files: dict) -> bytes:
    """{경로: bytes 또는 (bytes, 모드)} → tar 바이트 (테스트·에이전트 패키징용). 소유자는 1000, 기본 모드 0644."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, val in files.items():
            data, mode = val if isinstance(val, tuple) else (val, 0o644)
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.uid, ti.gid = len(data), mode, 1000, 1000
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def _mask(text: str, secrets_: list) -> str:
    for v in sorted({s for s in secrets_ if s and len(s) >= 3}, key=len, reverse=True):
        text = text.replace(v, "***")
    return text


class _LogParser:
    """로그 스트림을 줄 단위로 나눠 결과 마커 줄과 일반 로그를 분리한다. 메모리를 한도 안으로 묶는다."""

    def __init__(self, token: str, log_cap: int, result_cap: int):
        self.marker = f"__FN_RESULT_{token}__ ".encode()
        self.log_cap, self.result_cap = log_cap, result_cap
        self.log = bytearray()
        self.truncated = False
        self.result_line: Optional[bytes] = None
        self.result_too_large = False
        self._partial = bytearray()
        self._discarding = False

    def _line(self, line: bytes) -> None:
        if line.startswith(self.marker):
            body = line[len(self.marker):]
            if len(body) > self.result_cap:
                self.result_too_large = True
            else:
                self.result_line = body
            return
        if len(self.log) >= self.log_cap:
            self.truncated = True
            return
        room = self.log_cap - len(self.log)
        if len(line) + 1 > room:
            self.log += line[:room]
            self.truncated = True
        else:
            self.log += line + b"\n"

    def feed(self, chunk: bytes) -> None:
        self._partial += chunk
        limit = max(self.result_cap, self.log_cap) + len(self.marker) + 64
        while True:
            i = self._partial.find(b"\n")
            if self._discarding:  # 너무 긴 줄의 나머지: 줄바꿈이 올 때까지 버린다
                if i < 0:
                    self._partial.clear()
                    return
                del self._partial[:i + 1]
                self._discarding = False
                continue
            if i < 0:
                if len(self._partial) > limit:  # 줄바꿈 없이 한도를 넘는 줄
                    if self._partial.startswith(self.marker[: min(len(self.marker), len(self._partial))]):
                        self.result_too_large = True  # 결과 마커 줄이 한도를 넘는다
                    else:
                        self._line(bytes(self._partial[: self.log_cap]))
                    self._partial.clear()
                    self._discarding = True
                return
            line = bytes(self._partial[:i])
            del self._partial[:i + 1]
            self._line(line.rstrip(b"\r"))

    def finish(self) -> None:
        if self._partial:
            self._line(bytes(self._partial))
            self._partial.clear()


class DockerRuntime:
    """Docker SDK 로 컨테이너를 직접 만든다. SDK 는 동기라서 전부 스레드에서 실행한다."""

    def _client(self):
        import docker

        return docker.from_env()

    async def run(self, spec: RunSpec, cancel: asyncio.Event) -> RunOutcome:
        flag = threading.Event()
        loop = asyncio.get_running_loop()
        fut = loop.run_in_executor(None, self._run_sync, spec, flag)

        async def watch():
            await cancel.wait()
            flag.set()

        w = asyncio.create_task(watch())
        try:
            return await fut
        finally:
            w.cancel()

    def _run_sync(self, spec: RunSpec, cancel: threading.Event) -> RunOutcome:
        client = self._client()
        token = secrets.token_hex(12)
        tmpfs_mb = max(32, min(512, int(spec.unpacked_bytes * 1.3 / _MB) + 16))  # 패키지는 메모리(tmpfs)에 풀리므로 메모리 한도에 더한다
        mem = spec.memory_mb + tmpfs_mb + 64
        env = {**{k: str(v) for k, v in spec.env.items()}, "FN_RUN_ID": spec.run_id, "FN_FUNCTION": spec.function, "FN_VERSION": str(spec.version),
               "FN_RESULT_TOKEN": token, "FN_TIMEOUT_MS": str(spec.timeout_s * 1000), "FN_MEMORY_MB": str(spec.memory_mb), "HOME": "/tmp"}
        network = "bridge" if (spec.allow_network and settings.FUNCTION_ALLOW_NETWORK) else "none"
        t0 = time.monotonic()
        container = None
        try:
            container = client.containers.create(
                image=image_for(spec.runtime), name=f"fn-{spec.run_id[:8]}-{secrets.token_hex(3)}", labels={LABEL: spec.run_id},
                environment=env, user="1000:1000", network_mode=network, read_only=True,
                tmpfs={"/tmp": "size=64m,mode=1777", "/var/task": f"size={tmpfs_mb}m,mode=755,uid=1000,gid=1000,exec"},  # exec: 패키지의 .so·실행 파일을 쓸 수 있게
                mem_limit=f"{mem}m", memswap_limit=f"{mem}m", nano_cpus=int(spec.cpu * 1e9), pids_limit=128,
                cap_drop=["ALL"], security_opt=["no-new-privileges"], init=True, stdin_open=True, tty=False,
                ulimits=[__import__("docker").types.Ulimit(name="nofile", soft=1024, hard=1024)],
                log_config={"Type": "json-file", "Config": {"max-size": "4m", "max-file": "1"}},
            )
            sock = container.attach_socket(params={"stdin": 1, "stream": 1})
            container.start()
            raw = getattr(sock, "_sock", sock)
            if spec.package_path:
                raw.sendall(b"PKG %d\n" % spec.package_size)
                sent = 0
                with gzip.open(spec.package_path, "rb") as pf:
                    for chunk in iter(lambda: pf.read(64 * 1024), b""):
                        raw.sendall(chunk)
                        sent += len(chunk)
                if sent != spec.package_size:
                    raise RuntimeError(f"패키지 크기가 기록과 다릅니다 ({sent} != {spec.package_size})")
                raw.sendall(b"EVT %d\n" % len(spec.event) + spec.event)
            else:
                raw.sendall(b"PKG %d\n" % len(spec.package_tar) + spec.package_tar + b"EVT %d\n" % len(spec.event) + spec.event)
            started = time.monotonic()
            cold_ms = int((started - t0) * 1000)

            parser = _LogParser(token, settings.FUNCTION_LOG_MAX_KB * 1024, settings.FUNCTION_RESULT_MAX_KB * 1024)

            def read_logs():
                try:
                    for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=True):
                        parser.feed(chunk)
                except Exception:  # noqa: BLE001  컨테이너가 사라지면 스트림이 끊긴다
                    pass

            reader = threading.Thread(target=read_logs, daemon=True)
            reader.start()

            status = None
            deadline = started + spec.timeout_s
            while True:
                if cancel.is_set():
                    status = "cancelled"
                    break
                if time.monotonic() > deadline:
                    status = "timeout"
                    break
                try:
                    container.reload()
                except Exception:  # noqa: BLE001
                    break
                if container.status in ("exited", "dead"):
                    break
                time.sleep(0.05)
            if status:
                try:
                    container.kill()
                except Exception:  # noqa: BLE001  이미 끝났을 수 있다
                    pass
            try:
                container.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
            reader.join(timeout=5)
            parser.finish()
            try:
                container.reload()
            except Exception:  # noqa: BLE001
                pass
            st = container.attrs.get("State", {})
            exit_code, oom = st.get("ExitCode"), bool(st.get("OOMKilled"))
            duration_ms = int((time.monotonic() - started) * 1000)
            log = _mask(parser.log.decode("utf-8", errors="replace"), spec.secret_values)
            out = RunOutcome(status="failed", exit_code=exit_code, log=log, log_truncated=parser.truncated, cold_start_ms=cold_ms, duration_ms=duration_ms, oom=oom)
            if status:
                out.status = status
                out.error = {"type": "Timeout" if status == "timeout" else "Cancelled", "message": f"{spec.timeout_s}초 제한 시간을 넘어 중단되었습니다" if status == "timeout" else "사용자가 실행을 취소했습니다"}
                return out
            if oom:
                out.error = {"type": "OutOfMemory", "message": f"메모리 한도({spec.memory_mb}MB)를 넘어 종료되었습니다"}
                return out
            if parser.result_too_large:
                out.error = {"type": "ResultTooLarge", "message": f"결과가 {settings.FUNCTION_RESULT_MAX_KB}KB 를 넘습니다"}
                return out
            if parser.result_line is not None:
                try:
                    payload = json.loads(parser.result_line)
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and payload.get("ok") is True:
                    out.status, out.result = "succeeded", payload.get("result")
                    return out
                if isinstance(payload, dict):
                    err = payload.get("error") or {}
                    out.error = {"type": str(err.get("type", "Error")), "message": _mask(str(err.get("message", "")), spec.secret_values)}
                    return out
            out.error = {"type": "NoResult", "message": f"결과 없이 종료되었습니다 (exit code {exit_code})"}
            return out
        except Exception as e:  # noqa: BLE001
            logger.exception("[functions] 실행 실패 run=%s", spec.run_id)
            msg = str(e)
            if "No such image" in msg or "not found" in msg.lower() and "image" in msg.lower():
                msg = f"런타임 이미지가 없습니다: {image_for(spec.runtime)} (infra/functions/build.sh 로 만드세요)"
            return RunOutcome(status="failed", error={"type": "Infrastructure", "message": msg[:500]}, cold_start_ms=int((time.monotonic() - t0) * 1000))
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001  남은 것은 고아 정리가 치운다
                    logger.warning("[functions] 컨테이너 제거 실패 run=%s", spec.run_id)

    async def cleanup_orphans(self) -> int:
        def _clean() -> int:
            n = 0
            for c in self._client().containers.list(all=True, filters={"label": LABEL}):
                try:
                    c.remove(force=True)
                    n += 1
                except Exception:  # noqa: BLE001
                    pass
            return n

        return await asyncio.get_running_loop().run_in_executor(None, _clean)


runtime: RuntimeBackend = DockerRuntime()

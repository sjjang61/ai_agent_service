"""작업공간(sandbox /workspace) 파일·명령 도구 9종.

read_file / write_file / edit_file / grep_file / delete_file / download_file /
publish_file / exec_command / read_image
"""
import asyncio
import ipaddress
import posixpath
import shlex
import socket
import uuid
from typing import Optional
from urllib.parse import unquote, urljoin, urlparse

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import load

from app.config import settings

WORKSPACE = "/workspace"
MAX_READ_BYTES = 5 * 1024 * 1024
MAX_WRITE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_CHARS = 30000
_BLOCKED_PREFIXES = ("rm -rf /", "mkfs", "dd if=", ":(){:|:&};:")


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────
def resolve_path(path: str) -> str:
    """사용자 입력 경로를 /workspace 하위 절대경로로 정규화. 벗어나면 ValueError."""
    p = (path or "").strip()
    if not p:
        raise ValueError("path 가 비어 있습니다")
    if not p.startswith("/"):
        p = f"{WORKSPACE}/{p}"
    n = posixpath.normpath(p)
    if n != WORKSPACE and not n.startswith(WORKSPACE + "/"):
        raise ValueError("작업공간(/workspace) 밖의 경로는 사용할 수 없습니다")
    return n


async def _kill_run(container_id: str, run_id: str):
    """환경변수 AGENT_RUN_ID 가 일치하는 프로세스(자식 포함)를 종료한다."""
    cmd = (
        "for d in /proc/[0-9]*; do pid=${d#/proc/}; "
        f"if tr '\\0' '\\n' < $d/environ 2>/dev/null | grep -qx 'AGENT_RUN_ID={run_id}'; then kill -9 $pid 2>/dev/null; fi; done"
    )
    try:
        await _manager().exec_command(container_id, cmd, timeout=15)
    except Exception:
        pass


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head, tail = int(limit * 0.6), int(limit * 0.3)
    return f"{text[:head]}\n...[{len(text) - head - tail} chars truncated]...\n{text[-tail:]}"


async def _container(user_id: str) -> str:
    from app.db.session import AsyncSessionLocal
    from app.services.sandbox_service import SandboxService

    async with AsyncSessionLocal() as db:
        sb = await SandboxService.get_or_create_sandbox(user_id, db)
        return sb.container_id


def _manager():
    from app.services.sandbox_service import sandbox_manager

    return sandbox_manager


async def _read_text(user_id: str, path: str) -> tuple[str, str, int]:
    """(절대경로, 텍스트, mode). 바이너리면 ValueError."""
    full = resolve_path(path)
    data, mode = await _manager().read_file(await _container(user_id), full, MAX_READ_BYTES)
    if b"\x00" in data[:8192]:
        raise ValueError("바이너리 파일입니다 (이미지는 read_image, 그 외는 exec_command 를 사용하세요)")
    return full, data.decode("utf-8", errors="replace"), mode


def _fmt_err(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return f"Error: 파일 또는 경로를 찾을 수 없습니다: {e}"
    if isinstance(e, IsADirectoryError):
        return f"Error: 디렉터리입니다 (파일 경로를 지정하세요): {e}"
    return f"Error: {type(e).__name__}: {e}"


def _numbered(lines: list[str], start: int) -> str:
    return "\n".join(f"{start + i:>6}\t{l.rstrip(chr(10)).rstrip(chr(13))}" for i, l in enumerate(lines))


class _AsyncTool(BaseTool):
    user_id: str = ""

    def _run(self, *args, **kwargs) -> str:  # 에이전트는 비동기 경로(_arun)만 사용한다
        return "This tool supports async execution only"


# ── read_file ────────────────────────────────────────────────────────────────
class ReadFileInput(BaseModel):
    path: str = Field(description="File path (relative to /workspace)")
    start_line: Optional[int] = Field(default=None, description="First line to read (1-based). Omit to read from the top")
    end_line: Optional[int] = Field(default=None, description="Last line to read (inclusive). Omit to read to the end")


class ReadFileTool(_AsyncTool):
    name: str = "read_file"
    description: str = (
        "Read a text file in the workspace. Returns lines prefixed with line numbers "
        "(use them with edit_file). Optionally read only a line range."
    )
    args_schema: type[BaseModel] = ReadFileInput

    async def _arun(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        try:
            full, text, _ = await _read_text(self.user_id, path)
            lines = text.splitlines(keepends=True)
            total = len(lines)
            s = max(start_line or 1, 1)
            e = min(end_line or total, total)
            if total == 0:
                return f"[{full}] (empty file)"
            if s > total:
                return f"Error: start_line {s} 이 파일 길이({total}줄)를 넘습니다"
            if e < s:
                return "Error: end_line 은 start_line 보다 작을 수 없습니다"
            body = _truncate(_numbered(lines[s - 1:e], s))
            return f"[{full}] lines {s}-{e} of {total}\n{body}"
        except Exception as e:
            return _fmt_err(e)


# ── write_file ───────────────────────────────────────────────────────────────
class WriteFileInput(BaseModel):
    path: str = Field(description="File path to create or overwrite (relative to /workspace). Parent directories are created")
    content: str = Field(description="Full text content to save")
    publish: bool = Field(default=False, description="If true, also create a public download link for the saved file")


class WriteFileTool(_AsyncTool):
    name: str = "write_file"
    description: str = (
        "Create a new file or overwrite an existing one with the given content. "
        "Set publish=true to also get a public download link."
    )
    args_schema: type[BaseModel] = WriteFileInput

    async def _arun(self, path: str, content: str, publish: bool = False) -> str:
        try:
            full = resolve_path(path)
            if full == WORKSPACE:
                return "Error: 파일 경로를 지정하세요"
            data = content.encode("utf-8")
            if len(data) > MAX_WRITE_BYTES:
                return f"Error: 한 번에 쓸 수 있는 최대 크기는 {MAX_WRITE_BYTES // (1024 * 1024)}MB 입니다"
            await _manager().write_file(await _container(self.user_id), full, data)
            msg = f"Saved {len(data)} bytes to {full}"
            if publish:
                from app.services.publish_service import publish as do_publish

                info = do_publish(self.user_id, posixpath.basename(full), data)
                msg += f"\nPublic download link (expires {info['expires_at']}): {info['url']}"
            return msg
        except Exception as e:
            return _fmt_err(e)


# ── edit_file ────────────────────────────────────────────────────────────────
class EditFileInput(BaseModel):
    path: str = Field(description="File path (relative to /workspace)")
    start_line: int = Field(description="First line to replace (1-based). Use total_lines+1 to append at the end")
    end_line: Optional[int] = Field(default=None, description="Last line to replace (inclusive). Omit to replace only start_line")
    new_content: str = Field(description="Replacement text for the line range. Empty string deletes those lines")


class EditFileTool(_AsyncTool):
    name: str = "edit_file"
    description: str = (
        "Edit an existing text file by replacing a line range (or a single line) with new content. "
        "Read the file with read_file first to get the correct line numbers."
    )
    args_schema: type[BaseModel] = EditFileInput

    async def _arun(self, path: str, start_line: int, new_content: str, end_line: Optional[int] = None) -> str:
        try:
            full, text, mode = await _read_text(self.user_id, path)
            lines = text.splitlines(keepends=True)
            total = len(lines)
            # end_line 생략: 한 줄 교체 (단, 파일 끝+1 위치면 추가)
            end = end_line if end_line is not None else min(start_line, total)
            if start_line < 1 or start_line > total + 1:
                return f"Error: start_line 은 1~{total + 1} 이어야 합니다 (파일 {total}줄)"
            if end < start_line - 1 or end > total:
                return f"Error: end_line 은 {start_line}~{total} 이어야 합니다"

            new = new_content
            # 뒤에 이어지는 줄이 있거나 교체된 마지막 줄이 개행으로 끝났다면 줄바꿈을 보존한다
            follows = end < total or (end >= start_line and lines[end - 1].endswith("\n"))
            if new and not new.endswith("\n") and follows:
                new += "\n"
            if start_line == total + 1 and new and lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"  # 마지막 줄에 개행이 없던 파일에 이어 붙이기
            new_lines = new.splitlines(keepends=True) if new else []
            result = lines[: start_line - 1] + new_lines + lines[end:]
            data = "".join(result).encode("utf-8")
            if len(data) > MAX_WRITE_BYTES:
                return "Error: 결과 파일이 너무 큽니다"
            await _manager().write_file(await _container(self.user_id), full, data, mode=mode & 0o777 or 0o644)

            ctx_s = max(start_line - 2, 1)
            ctx_e = min(start_line - 1 + len(new_lines) + 2, len(result))
            preview = _numbered(result[ctx_s - 1:ctx_e], ctx_s) if result else "(empty file)"
            return f"Edited {full}: replaced lines {start_line}-{end} with {len(new_lines)} line(s). Now {len(result)} lines.\n{preview}"
        except Exception as e:
            return _fmt_err(e)


# ── grep_file ────────────────────────────────────────────────────────────────
class GrepInput(BaseModel):
    pattern: str = Field(description="String or regular expression to search for")
    path: str = Field(default=".", description="File or directory to search (relative to /workspace). Directories are searched recursively")
    regex: bool = Field(default=True, description="Treat pattern as an extended regex (true) or a literal string (false)")
    ignore_case: bool = Field(default=False, description="Case-insensitive search")
    max_results: int = Field(default=50, description="Maximum number of matching lines to return (max 500)")


class GrepFileTool(_AsyncTool):
    name: str = "grep_file"
    description: str = (
        "Search files in the workspace for a string or regex pattern. "
        "Returns matching lines as path:line:text. Binary files are skipped."
    )
    args_schema: type[BaseModel] = GrepInput

    async def _arun(self, pattern: str, path: str = ".", regex: bool = True,
                    ignore_case: bool = False, max_results: int = 50) -> str:
        try:
            target = WORKSPACE if path.strip() in ("", ".") else resolve_path(path)
            limit = min(max(max_results, 1), 500)
            flags = "-rnI" + ("i" if ignore_case else "") + ("E" if regex else "F")
            cmd = f"cd {WORKSPACE} && grep {flags} --color=never -- {shlex.quote(pattern)} {shlex.quote(target)}"
            code, out, err = await _manager().exec_command(await _container(self.user_id), cmd, timeout=30)
            if code == 1:
                return "No matches found."
            if code not in (0, 1):
                return f"Error: grep failed (exit {code}): {err.strip()[:300]}"
            lines = out.splitlines()
            shown = [l.replace(f"{WORKSPACE}/", "", 1) for l in lines[:limit]]
            more = f"\n... {len(lines) - limit} more match(es) not shown" if len(lines) > limit else ""
            return _truncate("\n".join(shown)) + more
        except Exception as e:
            return _fmt_err(e)


# ── delete_file ──────────────────────────────────────────────────────────────
class DeleteFileInput(BaseModel):
    path: str = Field(description="File or directory path to delete (relative to /workspace)")


class DeleteFileTool(_AsyncTool):
    name: str = "delete_file"
    description: str = "Delete a file or directory (recursively) in the workspace. The workspace root itself cannot be deleted."
    args_schema: type[BaseModel] = DeleteFileInput

    async def _arun(self, path: str) -> str:
        try:
            full = resolve_path(path)
            if full == WORKSPACE:
                return "Error: 작업공간 루트는 삭제할 수 없습니다"
            cid = await _container(self.user_id)
            code, _, _ = await _manager().exec_command(cid, f"test -e {shlex.quote(full)}", timeout=15)
            if code != 0:
                return f"Error: 파일 또는 경로를 찾을 수 없습니다: {full}"
            code, _, err = await _manager().exec_command(cid, f"rm -rf -- {shlex.quote(full)}", timeout=30)
            return f"Deleted {full}" if code == 0 else f"Error: {err.strip()[:300]}"
        except Exception as e:
            return _fmt_err(e)


# ── download_file ────────────────────────────────────────────────────────────
def _assert_public_host(host: str):
    """내부망·루프백·링크로컬 등으로 향하는 URL 차단 (SSRF 방지)."""
    infos = socket.getaddrinfo(host, None)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"허용되지 않는 주소입니다 (내부망/예약 대역): {host}")


async def _fetch(url: str, max_bytes: int) -> tuple[bytes, str, str]:
    """리다이렉트마다 호스트를 검증하며 내려받는다. (내용, content-type, 최종 URL)"""
    import httpx

    async with httpx.AsyncClient(follow_redirects=False, timeout=60) as client:
        for _ in range(6):
            u = urlparse(url)
            if u.scheme not in ("http", "https") or not u.hostname:
                raise ValueError("http/https URL 만 지원합니다")
            await asyncio.to_thread(_assert_public_host, u.hostname)
            async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0 (agent-download)"}) as r:
                if r.is_redirect and r.headers.get("location"):
                    url = urljoin(url, r.headers["location"])
                    continue
                if r.status_code != 200:
                    raise ValueError(f"다운로드 실패: HTTP {r.status_code}")
                if int(r.headers.get("content-length", 0) or 0) > max_bytes:
                    raise ValueError(f"파일이 너무 큽니다 (최대 {max_bytes // (1024 * 1024)}MB)")
                buf = bytearray()
                async for chunk in r.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > max_bytes:
                        raise ValueError(f"파일이 너무 큽니다 (최대 {max_bytes // (1024 * 1024)}MB)")
                return bytes(buf), r.headers.get("content-type", ""), url
    raise ValueError("리다이렉트가 너무 많습니다")


class DownloadFileInput(BaseModel):
    url: str = Field(description="http(s) URL of the file to download")
    path: Optional[str] = Field(default=None, description="Destination path in the workspace. Defaults to the file name from the URL")


class DownloadFileTool(_AsyncTool):
    name: str = "download_file"
    description: str = "Download a file from a public http(s) URL into the workspace. Internal network addresses are blocked."
    args_schema: type[BaseModel] = DownloadFileInput

    async def _arun(self, url: str, path: Optional[str] = None) -> str:
        try:
            data, ctype, final = await _fetch(url.strip(), settings.DOWNLOAD_MAX_MB * 1024 * 1024)
            name = path or posixpath.basename(unquote(urlparse(final).path)) or "download"
            full = resolve_path(name)
            if full == WORKSPACE:
                return "Error: 저장할 파일 경로를 지정하세요"
            await _manager().write_file(await _container(self.user_id), full, data)
            return f"Downloaded {len(data)} bytes ({ctype or 'unknown type'}) to {full}"
        except Exception as e:
            return _fmt_err(e)


# ── publish_file ─────────────────────────────────────────────────────────────
class PublishFileInput(BaseModel):
    path: str = Field(description="Existing file path in the workspace to publish")
    expires_hours: Optional[int] = Field(default=None, description="Link lifetime in hours (default 24, max 168)")


class PublishFileTool(_AsyncTool):
    name: str = "publish_file"
    description: str = (
        "Publish an existing workspace file as a public download link (anyone with the link can download until it expires). "
        "Use this to hand generated files (reports, images, archives) to the user."
    )
    args_schema: type[BaseModel] = PublishFileInput

    async def _arun(self, path: str, expires_hours: Optional[int] = None) -> str:
        try:
            from app.services.publish_service import publish

            full = resolve_path(path)
            data, _ = await _manager().read_file(
                await _container(self.user_id), full, settings.PUBLISH_MAX_MB * 1024 * 1024
            )
            info = publish(self.user_id, posixpath.basename(full), data, expires_hours)
            return f"Public download link (expires {info['expires_at']}, {info['size']} bytes): {info['url']}"
        except Exception as e:
            return _fmt_err(e)


# ── exec_command ─────────────────────────────────────────────────────────────
class ExecCommandInput(BaseModel):
    command: str = Field(description="Shell command to run in the sandbox (bash). Use for build, lint, test, convert, pip install, unzip, etc.")
    timeout: int = Field(default=120, description="Timeout in seconds (default 120, max 600)")
    workdir: Optional[str] = Field(default=None, description="Working directory (default /workspace)")


class ExecCommandTool(_AsyncTool):
    name: str = "exec_command"
    description: str = (
        "Run a shell command inside the sandbox to build, check, test or convert files. "
        "Returns stdout, stderr and the exit code. The process is killed when the timeout is reached."
    )
    args_schema: type[BaseModel] = ExecCommandInput

    async def _arun(self, command: str, timeout: int = 120, workdir: Optional[str] = None) -> str:
        if command.strip().startswith(_BLOCKED_PREFIXES):
            return f"Error: 차단된 명령어입니다: {command[:80]}"
        try:
            t = min(max(timeout, 5), 600)
            wd = resolve_path(workdir) if workdir else WORKSPACE
            inner = f"cd {shlex.quote(wd)} && {command}"
            run_id = uuid.uuid4().hex  # 취소 시 이 실행의 프로세스만 찾아 종료하기 위한 표식
            wrapped = f"AGENT_RUN_ID={run_id} timeout -k 5 {t} bash -c {shlex.quote(inner)}"
            cid = await _container(self.user_id)
            try:
                code, out, err = await _manager().exec_command(cid, wrapped, timeout=t + 15)
            except asyncio.CancelledError:
                # 사용자가 실행을 취소함: 컨테이너 안에서 계속 도는 프로세스를 정리한다 (백그라운드로 실행)
                asyncio.create_task(_kill_run(cid, run_id))
                raise
            parts = []
            if out:
                parts.append(f"STDOUT:\n{_truncate(out.rstrip())}")
            if err:
                parts.append(f"STDERR:\n{_truncate(err.rstrip())}")
            parts.append(f"Exit code: {code}" + (f" (timed out after {t}s)" if code == 124 else ""))
            return "\n".join(parts)
        except asyncio.TimeoutError:
            return "Error: 명령 실행 시간이 초과되었습니다"
        except Exception as e:
            return _fmt_err(e)


# ── read_image ───────────────────────────────────────────────────────────────
def _image_format(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


class ReadImageInput(BaseModel):
    path: str = Field(description="Image file path in the workspace (png, jpg, gif, webp)")
    question: Optional[str] = Field(default=None, description="What to look for. Defaults to a general description with text/layout/error details")


class ReadImageTool(_AsyncTool):
    name: str = "read_image"
    description: str = (
        "Analyze an image in the workspace with a vision model: read text (OCR), describe layout, "
        "charts and UI elements, or find error messages. Pass a specific question for best results."
    )
    args_schema: type[BaseModel] = ReadImageInput

    async def _arun(self, path: str, question: Optional[str] = None) -> str:
        try:
            from agno.agent import Agent
            from agno.media import Image

            from app.agent.agno_engine import build_agno_model

            full = resolve_path(path)
            data, _ = await _manager().read_file(await _container(self.user_id), full, MAX_IMAGE_BYTES)
            fmt = _image_format(data)
            if not fmt:
                return "Error: 지원하지 않는 이미지 형식입니다 (png, jpg, gif, webp)"
            prompt = question or load("image_analysis")
            agent = Agent(model=build_agno_model(settings.LLM_TYPE), markdown=False)
            out = await asyncio.wait_for(agent.arun(prompt, images=[Image(content=data, format=fmt)]), timeout=120)
            return str(out.content or "(no response)")
        except Exception as e:
            return _fmt_err(e)

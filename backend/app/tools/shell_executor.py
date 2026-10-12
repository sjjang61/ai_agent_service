import shlex
from typing import Optional

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

# sandbox 내에서 실행을 금지할 명령어 prefix (컨테이너는 이미 격리되어 있지만 추가 방어)
_BLOCKED_PREFIXES = ("rm -rf /", "mkfs", "dd if=", ":(){:|:&};:")


def _is_blocked(command: str) -> bool:
    stripped = command.strip()
    return any(stripped.startswith(p) for p in _BLOCKED_PREFIXES)


class ShellInput(BaseModel):
    command: str = Field(
        description=(
            "Shell command to execute inside the sandbox. "
            "Supports curl, wget, git, pip, unzip, tar, ls, cat, etc. "
            "Working directory is /workspace. "
            "Examples: "
            "'curl -L https://example.com/data.csv -o data.csv', "
            "'wget https://example.com/file.zip', "
            "'pip install pandas openpyxl', "
            "'unzip file.zip', "
            "'ls -la'"
        )
    )
    timeout: int = Field(
        default=120,
        description="Execution timeout in seconds (default 120, max 300)",
    )
    workdir: Optional[str] = Field(
        default=None,
        description="Working directory inside sandbox (default: /workspace)",
    )


class ShellExecutorTool(BaseTool):
    name: str = "shell_executor"
    description: str = (
        "Execute shell commands inside the secure sandbox environment. "
        "Use this to download files (curl/wget), install packages (pip), "
        "extract archives (unzip/tar), or run any shell operation. "
        "Files are saved under /workspace. "
        "Returns stdout, stderr, and exit code."
    )
    args_schema: type[BaseModel] = ShellInput
    user_id: str = ""

    def _run(self, command: str, timeout: int = 120, workdir: Optional[str] = None) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(command, timeout, workdir))
                    return future.result()
            return loop.run_until_complete(self._arun(command, timeout, workdir))
        except Exception as e:
            return f"Shell execution error: {e}"

    async def _arun(
        self, command: str, timeout: int = 120, workdir: Optional[str] = None
    ) -> str:
        if _is_blocked(command):
            return f"Error: 차단된 명령어입니다: {command[:80]}"

        # timeout 상한 300초
        timeout = min(max(timeout, 5), 300)

        try:
            from app.sandbox.manager import SandboxManager
            from app.db.session import AsyncSessionLocal
            from app.services.sandbox_service import SandboxService

            manager = SandboxManager()
            async with AsyncSessionLocal() as db:
                sb = await SandboxService.get_or_create_sandbox(self.user_id, db)

            # workdir 지정 시 cd 후 실행
            wd = workdir.rstrip("/") if workdir else "/workspace"
            full_cmd = f"cd {shlex.quote(wd)} && {command}"

            exit_code, stdout, stderr = await manager.exec_command(
                sb.container_id, full_cmd, timeout=timeout
            )

            parts = []
            if stdout:
                parts.append(f"STDOUT:\n{stdout.rstrip()}")
            if stderr:
                parts.append(f"STDERR:\n{stderr.rstrip()}")
            parts.append(f"Exit code: {exit_code}")
            return "\n".join(parts)

        except Exception as e:
            return f"Shell execution error: {e}"

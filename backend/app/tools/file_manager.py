from typing import Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool


class FileOperationInput(BaseModel):
    operation: Literal["read", "write", "list", "delete"] = Field(
        description="Operation: read, write, list, delete"
    )
    path: str = Field(description="File or directory path (relative to /workspace)")
    content: Optional[str] = Field(default=None, description="Content for write operation")


class FileManagerTool(BaseTool):
    name: str = "file_manager"
    description: str = (
        "Manage files in the sandbox workspace. "
        "Operations: read, write, list, delete."
    )
    args_schema: type[BaseModel] = FileOperationInput
    user_id: str = ""

    def _run(self, operation: str, path: str, content: str = None) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(operation, path, content))
                    return future.result()
            return loop.run_until_complete(self._arun(operation, path, content))
        except Exception as e:
            return f"File manager error: {e}"

    async def _arun(self, operation: str, path: str, content: str = None) -> str:
        try:
            from app.sandbox.manager import SandboxManager
            from app.db.session import AsyncSessionLocal
            from app.services.sandbox_service import SandboxService

            manager = SandboxManager()
            async with AsyncSessionLocal() as db:
                sb = await SandboxService.get_or_create_sandbox(self.user_id, db)
                full_path = f"/workspace/{path.lstrip('/')}"

                if operation == "read":
                    _, stdout, stderr = await manager.exec_command(
                        sb.container_id, f"cat {full_path}"
                    )
                    return stdout if stdout else f"Error: {stderr}"
                elif operation == "write":
                    escaped = repr(content or "")
                    cmd = f"python3 -c \"open('{full_path}', 'w').write({escaped})\""
                    _, _, stderr = await manager.exec_command(sb.container_id, cmd)
                    return "Written successfully" if not stderr else f"Error: {stderr}"
                elif operation == "list":
                    _, stdout, stderr = await manager.exec_command(
                        sb.container_id, f"ls -la {full_path}"
                    )
                    return stdout if stdout else f"Error: {stderr}"
                elif operation == "delete":
                    _, _, stderr = await manager.exec_command(
                        sb.container_id, f"rm -rf {full_path}"
                    )
                    return "Deleted" if not stderr else f"Error: {stderr}"
                return f"Unknown operation: {operation}"
        except Exception as e:
            return f"File manager error: {e}"

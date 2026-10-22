import time

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool


class CodeInput(BaseModel):
    code: str = Field(description="Python code to execute")
    filename: str = Field(default="", description="Optional filename to save as (e.g. 'analysis.py')")
    timeout: int = Field(default=30, description="Execution timeout in seconds")
    purpose: str = Field(
        default="",
        description="Why you run this, in Korean, one short phrase (max 30 chars) shown to the user as the step title, e.g. '패키지 설치', '순위 데이터 추출', '결과 파일 변환'. Always provide it.",
    )


class CodeExecutorTool(BaseTool):
    name: str = "code_executor"
    description: str = (
        "Execute Python code in a secure sandbox environment. "
        "Code is saved as a .py file in /workspace before execution. "
        "Returns the saved file path, stdout, and stderr output."
    )
    args_schema: type[BaseModel] = CodeInput
    user_id: str = ""
    sandbox_cid: str = ""  # 비어 있으면 사용자 공용 sandbox

    def _run(self, code: str, filename: str = "", timeout: int = 30, purpose: str = "") -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(code, filename, timeout))
                    return future.result()
            return loop.run_until_complete(self._arun(code, filename, timeout))
        except Exception as e:
            return f"Code execution error: {e}"

    async def _arun(self, code: str, filename: str = "", timeout: int = 30, purpose: str = "") -> str:
        try:
            from app.sandbox.manager import SandboxManager
            from app.db.session import AsyncSessionLocal
            from app.services.sandbox_service import SandboxService

            manager = SandboxManager()
            async with AsyncSessionLocal() as db:
                sb = await SandboxService.get_or_create_sandbox(self.user_id, db, self.sandbox_cid or None)

                # 파일명 결정 (지정 없으면 타임스탬프 사용)
                if filename:
                    safe_name = filename.replace("/", "_").strip()
                    if not safe_name.endswith(".py"):
                        safe_name += ".py"
                else:
                    ts = int(time.time() * 1000)
                    safe_name = f"script_{ts}.py"
                file_path = f"/workspace/{safe_name}"

                # 코드를 workspace 파일로 저장
                write_cmd = f"python3 -c \"open({repr(file_path)}, 'w').write({repr(code)})\""
                await manager.exec_command(sb.container_id, write_cmd)

                # 파일 실행
                exit_code, stdout, stderr = await manager.exec_command(
                    sb.container_id,
                    f"python3 {file_path}",
                    timeout=timeout,
                )

            result = [f"[saved: {file_path}]"]
            if stdout:
                result.append(f"STDOUT:\n{stdout}")
            if stderr:
                result.append(f"STDERR:\n{stderr}")
            result.append(f"Exit code: {exit_code}")
            return "\n".join(result)
        except Exception as e:
            return f"Code execution error: {e}"

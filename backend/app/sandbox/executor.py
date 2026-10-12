from app.sandbox.manager import SandboxManager

_manager = SandboxManager()


async def run_code(container_id: str, code: str, timeout: int = 30) -> dict:
    exit_code, stdout, stderr = await _manager.exec_command(
        container_id,
        f"python3 -c {repr(code)}",
        timeout=timeout,
    )
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}


async def run_command(container_id: str, command: str, timeout: int = 30) -> dict:
    exit_code, stdout, stderr = await _manager.exec_command(
        container_id, command, timeout=timeout
    )
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

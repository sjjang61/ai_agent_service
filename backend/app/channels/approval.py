"""메신저 실행의 위험 도구 승인. 도구를 호출하기 직전에 사용자에게 버튼으로 허용 여부를 묻는다."""
import json
from typing import Awaitable, Callable, Optional

from langchain_core.tools import BaseTool

# 읽기 전용 도구(검색·파일 읽기·위키·메모리 등)는 묻지 않는다. 아래는 부수효과가 있거나 임의 코드를 돌리는 도구다.
RISKY_TOOLS = {
    "exec_command", "shell_executor", "code_executor", "delete_file", "publish_file", "download_file",
    "call_mcp_tool", "run_mcp_code", "cli_browser_agent", "browser_action", "manage_schedule", "write_file", "edit_file",
    "generate_image", "generate_video", "upload_to_minio",  # 비용·공개 업로드
    "deploy_web_app",  # 외부에 열리는 포트로 앱을 공개
}

# approver(tool_name, summary) -> True(허용) / False(거부)
Approver = Callable[[str, str], Awaitable[bool]]

DENIED = "[Denied] 사용자가 이 작업을 거부했거나 응답하지 않았습니다. 같은 작업을 다시 시도하지 말고, 다른 방법이 있으면 제안하거나 상황을 설명하세요."


def summarize_call(name: str, kwargs: dict) -> str:
    """승인 요청에 보여줄 한 덩어리 요약 (길이 제한)."""
    purpose = str(kwargs.get("purpose") or "").strip()
    main = next((str(kwargs[k]) for k in ("command", "code", "path", "url", "prompt", "tool_name", "action", "task") if kwargs.get(k)), "")
    if not main:
        main = json.dumps(kwargs, ensure_ascii=False, default=str)
    main = main if len(main) <= 500 else main[:500] + "…"
    return (f"{purpose}\n" if purpose else "") + main


def gate_tools(tools: list[BaseTool], approver: Approver) -> list[BaseTool]:
    """위험 도구의 실행 직전에 approver 를 거치도록 각 도구 인스턴스의 _arun 을 감싼다."""
    for tool in tools:
        if tool.name not in RISKY_TOOLS or getattr(tool, "_gated", False):
            continue
        inner = tool._arun

        async def gated(*args, _inner=inner, _name=tool.name, **kwargs):
            if not await approver(_name, summarize_call(_name, kwargs)):
                return DENIED
            return await _inner(*args, **kwargs)

        object.__setattr__(tool, "_arun", gated)
        object.__setattr__(tool, "_gated", True)
    return tools

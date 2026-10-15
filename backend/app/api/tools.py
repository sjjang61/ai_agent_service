"""도구 목록 조회 API"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


class ToolInfo(BaseModel):
    name: str
    description: str
    group: str


class ToolGroup(BaseModel):
    group: str
    label: str
    icon: str
    tools: List[ToolInfo]


# 도구 정의 (그룹별로 정렬)
BUILTIN_TOOLS: List[ToolInfo] = [
    # Search & Browse
    ToolInfo(
        name="web_search",
        description="Search the web for current information. Use this to find up-to-date facts, news, or any information.",
        group="search",
    ),
    ToolInfo(
        name="web_crawler",
        description="Crawl a webpage and extract its content. Use this to read the full content of a specific URL.",
        group="search",
    ),
    # File Operations
    ToolInfo(
        name="read_file",
        description="Read a text file in the workspace. Returns lines prefixed with line numbers.",
        group="file",
    ),
    ToolInfo(
        name="write_file",
        description="Create a new file or overwrite an existing one with the given content.",
        group="file",
    ),
    ToolInfo(
        name="edit_file",
        description="Edit an existing text file by replacing a line range with new content.",
        group="file",
    ),
    ToolInfo(
        name="grep_file",
        description="Search files in the workspace for a string or regex pattern.",
        group="file",
    ),
    ToolInfo(
        name="delete_file",
        description="Delete a file or directory (recursively) in the workspace.",
        group="file",
    ),
    ToolInfo(
        name="read_image",
        description="Analyze an image in the workspace with a vision model: read text (OCR), describe layout, charts and UI elements.",
        group="file",
    ),
    # Code & Shell
    ToolInfo(
        name="code_executor",
        description="Execute Python code in a secure sandbox environment.",
        group="code",
    ),
    ToolInfo(
        name="exec_command",
        description="Run a shell command inside the sandbox to build, check, test or convert files.",
        group="code",
    ),
    # Share & Download
    ToolInfo(
        name="download_file",
        description="Download a file from a public http(s) URL into the workspace.",
        group="share",
    ),
    ToolInfo(
        name="publish_file",
        description="Publish an existing workspace file as a public download link.",
        group="share",
    ),
    # Visualization
    ToolInfo(
        name="create_widget",
        description="Turn part of the answer into a visual widget: comparison table, bar/line/pie chart, flowchart/diagram (Mermaid), or map with markers.",
        group="visualization",
    ),
    # Memory
    ToolInfo(
        name="memory_tool",
        description="Store and retrieve information for long-term memory across conversations.",
        group="memory",
    ),
    # Planning & Interaction
    ToolInfo(
        name="todo",
        description="Plan and track a multi-step task. The list is shown to the user as a checklist.",
        group="interaction",
    ),
    ToolInfo(
        name="narrate",
        description="Tell the user a short progress note during long, multi-step work.",
        group="interaction",
    ),
    ToolInfo(
        name="form_ask_user",
        description="Ask the user to choose among options or type a free-form answer, shown as a form in the chat.",
        group="interaction",
    ),
]

TOOL_GROUPS = {
    "search": {"label": "Search & Browse", "icon": "search"},
    "file": {"label": "File Operations", "icon": "folder"},
    "code": {"label": "Code & Shell", "icon": "terminal"},
    "share": {"label": "Share & Download", "icon": "share"},
    "visualization": {"label": "Visualization", "icon": "bar-chart"},
    "memory": {"label": "Memory", "icon": "database"},
    "interaction": {"label": "Planning & Interaction", "icon": "message-circle"},
}


@router.get("", response_model=List[ToolGroup])
async def list_tools(current_user: User = Depends(get_current_user)):
    """사용 가능한 도구 목록을 그룹별로 반환합니다."""
    grouped: dict[str, List[ToolInfo]] = {}
    for tool in BUILTIN_TOOLS:
        grouped.setdefault(tool.group, []).append(tool)

    result: List[ToolGroup] = []
    for group_key in ["search", "file", "code", "share", "visualization", "memory", "interaction"]:
        if group_key in grouped:
            meta = TOOL_GROUPS[group_key]
            result.append(
                ToolGroup(
                    group=group_key,
                    label=meta["label"],
                    icon=meta["icon"],
                    tools=grouped[group_key],
                )
            )
    return result

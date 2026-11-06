"""도구 목록 조회 API"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.services.tool_settings_service import ToolSettingsService

router = APIRouter()


class ToolInfo(BaseModel):
    name: str
    description: str
    group: str
    enabled: bool = True  # 사용자가 이 도구를 켜 두었는지 (끄면 에이전트가 쓰지 못한다)


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
    ToolInfo(
        name="cli_browser_agent",
        description="Operate a real browser (login, clicks, forms, JavaScript pages). A browser sub-agent does the whole task and reports back.",
        group="search",
    ),
    ToolInfo(
        name="search_documents",
        description="Search the documents you uploaded to this conversation (RAG).",
        group="search",
    ),
    ToolInfo(
        name="search_wiki",
        description="Search your saved personal wiki pages for relevant content.",
        group="search",
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
    ToolInfo(
        name="generate_image",
        description="Generate a new image from a text description, save it in the workspace and upload it to MinIO for a public URL.",
        group="share",
    ),
    ToolInfo(
        name="generate_video",
        description="Generate a short video clip (4-10s) from a text description (optionally with reference images), save it in the workspace and upload it to MinIO for a public URL.",
        group="share",
    ),
    ToolInfo(
        name="upload_to_minio",
        description="Upload one workspace image or video to the public MinIO bucket and return its public URL.",
        group="share",
    ),
    ToolInfo(
        name="deploy_web_app",
        description="Deploy a web app built in the workspace (static build output or a server app with .scripts/start.sh) and get a browser URL on its own port; sleeps when idle and wakes on request.",
        group="share",
    ),
    ToolInfo(
        name="manage_web_app",
        description="List, start, stop, delete deployed web apps and read their logs.",
        group="share",
    ),
    # Visualization
    ToolInfo(
        name="create_widget",
        description="Turn part of the answer into a visual widget: comparison table, bar/line/pie chart, flowchart/diagram (Mermaid), or map with markers.",
        group="visualization",
    ),
    ToolInfo(
        name="register_skill",
        description="Register a skill created in the sandbox so it can be reused.",
        group="code",
    ),
    ToolInfo(
        name="manage_schedule",
        description="Create and manage scheduled tasks from the chat.",
        group="interaction",
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
async def list_tools(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """사용 가능한 도구 목록을 그룹별로 반환합니다 (각 도구의 켜짐 여부 포함)."""
    disabled = await ToolSettingsService.disabled_names(current_user.id, db)
    grouped: dict[str, List[ToolInfo]] = {}
    for tool in BUILTIN_TOOLS:
        grouped.setdefault(tool.group, []).append(tool.model_copy(update={"enabled": tool.name not in disabled}))

    result: List[ToolGroup] = []
    for group_key in ["search", "file", "code", "share", "visualization", "memory", "interaction"]:
        if group_key in grouped:
            meta = TOOL_GROUPS[group_key]
            result.append(ToolGroup(group=group_key, label=meta["label"], icon=meta["icon"], tools=grouped[group_key]))
    return result


class ToolEnabledRequest(BaseModel):
    enabled: bool


class ToolsEnabledRequest(BaseModel):
    names: List[str]
    enabled: bool


def _known(names: List[str]) -> None:
    known = {t.name for t in BUILTIN_TOOLS}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise HTTPException(status_code=404, detail=f"알 수 없는 도구입니다: {', '.join(unknown)}")


@router.put("/{tool_name}")
async def set_tool_enabled(
    tool_name: str,
    data: ToolEnabledRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """도구 하나를 켜거나 끕니다. 끈 도구는 이 사용자의 에이전트(채팅·예약·메신저)가 쓰지 못합니다."""
    _known([tool_name])
    await ToolSettingsService.set_enabled(current_user.id, [tool_name], data.enabled, db)
    return {"name": tool_name, "enabled": data.enabled}


@router.put("")
async def set_tools_enabled(
    data: ToolsEnabledRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """여러 도구(예: 한 그룹 전체)를 한 번에 켜거나 끕니다."""
    _known(data.names)
    await ToolSettingsService.set_enabled(current_user.id, data.names, data.enabled, db)
    return {"names": data.names, "enabled": data.enabled}

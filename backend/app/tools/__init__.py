from typing import Callable, List, Optional

from langchain_core.tools import BaseTool


async def get_builtin_tools(
    user_id: str,
    conversation_id: str = "",
    db_session_factory: Optional[Callable] = None,
    sandbox_cid: str = "",
) -> List[BaseTool]:
    """sandbox_cid: sandbox 도구가 쓸 sandbox. 대화방 id 면 그 대화방 전용, 빈 문자열이면 사용자 공용 sandbox."""
    from app.tools.web_search import WebSearchTool
    from app.tools.crawler import WebCrawlerTool
    from app.tools.code_executor import CodeExecutorTool
    from app.tools.file_manager import FileManagerTool
    from app.tools.shell_executor import ShellExecutorTool
    from app.tools.memory_tool import MemoryTool
    from app.tools.widget_tool import CreateWidgetTool
    from app.tools.rag_tool import RAGTool
    from app.tools.wiki_tool import SearchWikiTool
    from app.tools.workspace_tools import (
        DeleteFileTool, DownloadFileTool, EditFileTool, ExecCommandTool, GrepFileTool,
        PublishFileTool, ReadFileTool, ReadImageTool, WriteFileTool,
    )

    from app.config import settings
    from app.services import object_storage
    from app.tools.image_tools import GenerateImageTool, UploadToMinioTool
    from app.tools.video_tools import GenerateVideoTool

    image_tools: List[BaseTool] = []
    if settings.IMAGE_GENERATION_ENABLED and settings.OPENAI_API_KEY:
        image_tools.append(GenerateImageTool(user_id=user_id, sandbox_cid=sandbox_cid, conversation_id=conversation_id))
    if settings.VIDEO_GENERATION_ENABLED and (settings.VIDEO_API_KEY or settings.GOOGLE_API_KEY):
        image_tools.append(GenerateVideoTool(user_id=user_id, sandbox_cid=sandbox_cid, conversation_id=conversation_id))
    if object_storage.enabled():
        image_tools.append(UploadToMinioTool(user_id=user_id, sandbox_cid=sandbox_cid))

    return image_tools + [
        WebSearchTool(),
        WebCrawlerTool(),
        CodeExecutorTool(user_id=user_id, sandbox_cid=sandbox_cid),
        FileManagerTool(user_id=user_id, sandbox_cid=sandbox_cid),
        ShellExecutorTool(user_id=user_id, sandbox_cid=sandbox_cid),
        MemoryTool(
            user_id=user_id,
            conversation_id=conversation_id,
            db_session_factory=db_session_factory,
        ),
        RAGTool(conversation_id=conversation_id),
        SearchWikiTool(user_id=user_id),
        ReadFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        WriteFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        EditFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        GrepFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        DeleteFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        DownloadFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        PublishFileTool(user_id=user_id, sandbox_cid=sandbox_cid),
        ExecCommandTool(user_id=user_id, sandbox_cid=sandbox_cid),
        ReadImageTool(user_id=user_id, sandbox_cid=sandbox_cid),
        CreateWidgetTool(),
    ]

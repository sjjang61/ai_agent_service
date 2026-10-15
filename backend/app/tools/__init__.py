from typing import Callable, List, Optional

from langchain_core.tools import BaseTool


async def get_builtin_tools(
    user_id: str,
    conversation_id: str = "",
    db_session_factory: Optional[Callable] = None,
) -> List[BaseTool]:
    from app.tools.web_search import WebSearchTool
    from app.tools.crawler import WebCrawlerTool
    from app.tools.code_executor import CodeExecutorTool
    from app.tools.file_manager import FileManagerTool
    from app.tools.shell_executor import ShellExecutorTool
    from app.tools.memory_tool import MemoryTool
    from app.tools.widget_tool import CreateWidgetTool
    from app.tools.rag_tool import RAGTool
    from app.tools.workspace_tools import (
        DeleteFileTool, DownloadFileTool, EditFileTool, ExecCommandTool, GrepFileTool,
        PublishFileTool, ReadFileTool, ReadImageTool, WriteFileTool,
    )

    return [
        WebSearchTool(),
        WebCrawlerTool(),
        CodeExecutorTool(user_id=user_id),
        FileManagerTool(user_id=user_id),
        ShellExecutorTool(user_id=user_id),
        MemoryTool(
            user_id=user_id,
            conversation_id=conversation_id,
            db_session_factory=db_session_factory,
        ),
        RAGTool(conversation_id=conversation_id),
        ReadFileTool(user_id=user_id),
        WriteFileTool(user_id=user_id),
        EditFileTool(user_id=user_id),
        GrepFileTool(user_id=user_id),
        DeleteFileTool(user_id=user_id),
        DownloadFileTool(user_id=user_id),
        PublishFileTool(user_id=user_id),
        ExecCommandTool(user_id=user_id),
        ReadImageTool(user_id=user_id),
        CreateWidgetTool(),
    ]

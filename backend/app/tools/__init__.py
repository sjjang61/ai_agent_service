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

    return [
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

from typing import List

from langchain_core.tools import BaseTool


async def get_builtin_tools(user_id: str) -> List[BaseTool]:
    from app.tools.web_search import WebSearchTool
    from app.tools.crawler import WebCrawlerTool
    from app.tools.code_executor import CodeExecutorTool
    from app.tools.file_manager import FileManagerTool
    from app.tools.shell_executor import ShellExecutorTool
    from app.tools.memory_tool import MemoryTool

    return [
        WebSearchTool(),
        WebCrawlerTool(),
        CodeExecutorTool(user_id=user_id),
        FileManagerTool(user_id=user_id),
        ShellExecutorTool(user_id=user_id),
        MemoryTool(user_id=user_id),
    ]

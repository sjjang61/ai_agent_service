from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from app.config import settings


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum number of results")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current information. "
        "Use this to find up-to-date facts, news, or any information."
    )
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(query, max_results))
                    return future.result()
            return loop.run_until_complete(self._arun(query, max_results))
        except Exception as e:
            return f"Search error: {e}"

    async def _arun(self, query: str, max_results: int = 5) -> str:
        if settings.TAVILY_API_KEY:
            try:
                from tavily import TavilyClient
                client = TavilyClient(api_key=settings.TAVILY_API_KEY)
                results = client.search(query=query, max_results=max_results)
                output = []
                for r in results.get("results", []):
                    output.append(
                        f"Title: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('content')}\n"
                    )
                return "\n---\n".join(output) if output else "No results found."
            except Exception as e:
                return f"Search error: {e}"
        return f"Web search not configured. Set TAVILY_API_KEY. Query: {query}"

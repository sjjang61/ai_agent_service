from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool
from app.config import settings


class CrawlerInput(BaseModel):
    url: str = Field(description="URL to crawl and extract content from")
    extract_text: bool = Field(default=True, description="Extract text content only")


class WebCrawlerTool(BaseTool):
    name: str = "web_crawler"
    description: str = (
        "Crawl a webpage and extract its content. "
        "Use this to read the full content of a specific URL."
    )
    args_schema: type[BaseModel] = CrawlerInput

    def _run(self, url: str, extract_text: bool = True) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self._arun(url, extract_text))
                    return future.result()
            return loop.run_until_complete(self._arun(url, extract_text))
        except Exception as e:
            return f"Crawler error: {e}"

    async def _arun(self, url: str, extract_text: bool = True) -> str:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=settings.CRAWLER_HEADLESS)
                page = await browser.new_page()
                await page.goto(url, timeout=settings.CRAWLER_TIMEOUT_MS)
                if extract_text:
                    content = await page.inner_text("body")
                else:
                    content = await page.content()
                await browser.close()
                return content[:10000]
        except Exception as e:
            return f"Crawler error: {e}"

"""모니터링(Opik/Langfuse) P0 검증 스크립트. 실제 사내 LLM 으로 대표 시나리오를 돌려 트레이스를 보낸다 (브라우저·검색 도구는 가짜).

사용 (LLM_TYPE 으로 쓸 모델을 고른다. 사내 게이트웨이에 닿지 않으면 LLM_TYPE=openai):
  LLM_TYPE=openai AGENT_MONITORING_TYPE=opik OPIK_URL=http://localhost:15174 PYTHONPATH=. uv run python scripts/monitoring_poc.py [시나리오 …]
시나리오: delegate | nostream | browser | parallel | error | langchain   (비우면 전부)
  nostream = 스트리밍 없는 실행 경로(PET 기본 경로)로 delegate 를 돌린다. langchain 은 MONITORING_LANGCHAIN=true 일 때만 기록된다.
끝나면 이 프로세스가 보낸 트레이스의 session id(prefix)를 출력한다 → scripts/monitoring_check.py 로 서버에서 트리를 확인한다.
"""
import asyncio
import sys
import time
import uuid
from typing import Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel

RUN = f"poc-{uuid.uuid4().hex[:6]}"


class WebSearchIn(BaseModel):
    query: str


class FakeSearch(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for current information."
    args_schema: type[BaseModel] = WebSearchIn

    def _run(self, *a, **k) -> str:
        return "x"

    async def _arun(self, query: str) -> str:
        await asyncio.sleep(0.2)
        return f"Title: 삼성전자 뉴스룸\nURL: https://news.samsung.com\nContent: '{query}' 관련 최신 소식 3건 (가짜 결과)"


def snapshot(url: str) -> dict:
    els = [{"ref": i, "tag": "a", "label": f"링크 {i}", "href": f"{url}/{i}"} for i in range(1, 41)]
    return {"ok": True, "url": url, "title": f"가짜 페이지 {url}", "elements": els, "text": "가짜 페이지 본문 " * 60}


async def fake_browser_call(user_id, payload, timeout=90, sandbox_cid="", use_profile=True, session_id=""):
    await asyncio.sleep(0.3)
    return snapshot(payload.get("url") or "https://example.com")


def tools():
    from app.tools import browser_tools as bt

    bt.browser_call = fake_browser_call  # 실제 브라우저 대신 가짜 스냅샷
    return [FakeSearch(), bt.CliBrowserAgentTool(user_id="poc-user", login_enabled=False), bt.BrowserParallelTool(user_id="poc-user", login_enabled=False)]


async def run(name: str, prompt: str, setup=None) -> None:
    from app.agent.agno_engine import AgnoRunner
    from app.agent.orchestrator import SYSTEM_PROMPT, compose_prompt

    if setup:
        setup()
    sid = f"{RUN}-{name}"
    t0 = time.time()
    from app.config import settings

    runner = AgnoRunner(tools(), settings.LLM_TYPE, None, compose_prompt(SYSTEM_PROMPT, None))
    seq = []
    async for ev in runner.stream(prompt, [], sid, "poc-user"):
        if ev.get("type") in ("tool_call", "tool_result", "error"):
            seq.append(f"{ev['type']}:{ev.get('tool', '')}")
    print(f"[{name}] {time.time() - t0:.1f}s session={sid} events={seq[:12]}")


async def langchain_call() -> None:
    from app.agent.react_agent import AgentRunner

    t0 = time.time()
    out = await AgentRunner(tools=[]).llm.ainvoke("한 단어로만 답해: 하늘 색은?")
    print(f"[langchain] {time.time() - t0:.1f}s -> {str(out.content)[:30]!r}")


async def main(names: list[str]) -> None:
    from app.config import settings
    from app.core.monitoring import active_backend, setup_monitoring, shutdown_monitoring

    print("monitoring:", setup_monitoring() or "꺼짐", "| type:", settings.AGENT_MONITORING_TYPE, "| run:", RUN)
    want = lambda n: not names or n in names  # noqa: E731
    if want("delegate"):
        await run("delegate", "웹 검색으로 삼성전자 최근 뉴스를 찾아 한 줄로 알려줘.")
    if want("nostream"):
        import app.agent.agno_engine as eng

        def no_stream():
            eng._use_streaming = lambda llm_type: False  # PET_STREAMING=false 와 같은 경로

        await run("nostream", "웹 검색으로 삼성전자 최근 뉴스를 찾아 한 줄로 알려줘.", setup=no_stream)
        eng._use_streaming = lambda llm_type: True
    if want("browser"):
        await run("browser", "브라우저로 https://example.com 에 접속해서 페이지 제목을 알려줘.")
    if want("parallel"):
        await run("parallel", "브라우저에서 https://a.example.com 과 https://b.example.com 두 사이트를 동시에 열어 각각 제목을 비교해줘.")
    if want("error"):
        def bad():
            settings.PET_REASONING_EFFORT = "bogus"  # LLM 이 거부하는 값 (오류 스팬 확인용)
            settings.OPENAI_REASONING_EFFORT = "bogus"

        await run("error", "안녕", setup=bad)
        settings.PET_REASONING_EFFORT, settings.OPENAI_REASONING_EFFORT = "none", ""
    if want("langchain"):
        await langchain_call()
    shutdown_monitoring()  # 남은 트레이스 전송
    print("done. session prefix:", RUN, "| backend:", active_backend() or "-")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))

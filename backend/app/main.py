import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, chat, files, mcp, memory, sandbox, skills, tools, wiki, ws
from app.db.session import init_db
from app.config import settings

logger = logging.getLogger(__name__)


# ─── MCP SSE 연결 종료 로그 억제 ──────────────────────────────────────────────
# mcp/client/sse.py 내부의 sse_reader() 는 연결이 끊어질 때
# logger.exception("Error in sse_reader") 를 호출한다.
# SSE 서버가 idle timeout 등으로 연결을 정상적으로 끊을 때도 동일 로그가 발생하므로
# RemoteProtocolError / incomplete chunked read 는 DEBUG 레벨로 내려 콘솔 노이즈를 제거한다.

_MCP_SSE_SUPPRESS_MSGS = ("Error in sse_reader", "Error in post_writer")
_MCP_SSE_SUPPRESS_EXCS = ("RemoteProtocolError", "incomplete chunked read", "ClosedResourceError")


class _McpSseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "mcp.client.sse":
            return True

        msg = record.getMessage()
        if not any(m in msg for m in _MCP_SSE_SUPPRESS_MSGS):
            return True

        # exc_info 에 억제 대상 예외가 있으면 완전 드롭
        exc_info = record.exc_info
        if exc_info and exc_info[1] is not None:
            exc_str = f"{type(exc_info[1]).__name__}: {exc_info[1]}"
            if any(k in exc_str for k in _MCP_SSE_SUPPRESS_EXCS):
                return False  # 완전 제거 (핸들러 레벨 무관)

        return True  # 그 외 예상치 못한 MCP SSE 에러는 그대로 출력


def _setup_mcp_log_filter() -> None:
    mcp_sse_logger = logging.getLogger("mcp.client.sse")
    mcp_sse_logger.addFilter(_McpSseFilter())

    # asyncio 레벨의 미수집 태스크 예외도 같은 필터 적용
    def _asyncio_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        exc_str = f"{type(exc).__name__}: {exc}" if exc else context.get("message", "")
        if any(k in exc_str for k in _MCP_SSE_SUPPRESS_EXCS):
            logger.debug("[asyncio] MCP SSE 태스크 종료 (무시): %s", exc_str)
            return
        loop.default_exception_handler(context)

    asyncio.get_event_loop().set_exception_handler(_asyncio_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_mcp_log_filter()
    await init_db()
    from app.sandbox.reaper import run_idle_reaper

    reaper = asyncio.create_task(run_idle_reaper())
    yield
    reaper.cancel()


app = FastAPI(title="AI Agent Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(sandbox.router, prefix="/api/sandbox", tags=["sandbox"])
app.include_router(wiki.router, prefix="/api/wiki", tags=["wiki"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(ws.router, prefix="/ws", tags=["ws"])


@app.get("/health")
async def health():
    return {"status": "ok"}

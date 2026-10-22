"""MCP 도구 3종: load_mcp_tool / call_mcp_tool / run_mcp_code.

MCP 서버의 모든 도구 스키마를 매번 LLM 에 싣는 대신, 프롬프트에는 이름·한 줄 설명 목록만 두고
필요한 도구만 load_mcp_tool 로 스키마를 확인한 뒤 call_mcp_tool 로 호출한다.
대량 결과나 여러 호출의 연결·집계는 run_mcp_code 로 sandbox 안에서 파이썬 코드로 처리한다.
"""
import json
import shlex
from typing import Any, Optional

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

from app.agent.prompts import render

MAX_RESULT_CHARS = 30000
MAX_RPC_RESULT_BYTES = 1024 * 1024  # MCP 호출 결과 크기 제한 (1MB)
RPC_PREFIX = "@@MCP_RPC@@"
RUNNER_PATH = "/tmp/_mcp_runner.py"

# sandbox 안에서 실행되는 러너. 코드의 `mcp.call()` 은 stdout 으로 요청을 보내고 stdin 으로 결과를 받는다.
RUNNER_SOURCE = r'''
import json, sys

_PREFIX = "@@MCP_RPC@@"
_out, _in = sys.stdout, sys.stdin


class _MCP:
    def _rpc(self, payload):
        _out.write(_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
        _out.flush()
        line = _in.readline()
        if not line:
            raise RuntimeError("MCP bridge closed")
        resp = json.loads(line)
        if "error" in resp:
            raise RuntimeError(resp["error"])
        return resp["result"]

    def call(self, server, tool, arguments=None, **kwargs):
        """MCP 도구를 호출하고 결과 텍스트를 반환한다."""
        args = dict(arguments or {})
        args.update(kwargs)
        return self._rpc({"op": "call", "server": server, "tool": tool, "arguments": args})

    def call_json(self, server, tool, arguments=None, **kwargs):
        """call() 결과를 JSON 으로 파싱해 반환한다 (JSON 이 아니면 문자열 그대로)."""
        text = self.call(server, tool, arguments, **kwargs)
        try:
            return json.loads(text)
        except ValueError:
            return text

    def tools(self, server=None):
        """사용 가능한 MCP 도구 목록 [{server, name, description}]."""
        return self._rpc({"op": "list", "server": server})


mcp = _MCP()
src = open(sys.argv[1], encoding="utf-8").read()
exec(compile(src, "<run_mcp_code>", "exec"), {"mcp": mcp, "__name__": "__main__"})
'''


def _truncate(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...[{len(text) - limit} chars truncated. For large results use run_mcp_code to filter/aggregate]"


async def _clients(user_id: str, policy=None) -> dict:
    from app.db.session import AsyncSessionLocal
    from app.mcp.manager import MCPSessionManager
    from app.mcp.policy import apply_policy

    async with AsyncSessionLocal() as db:
        return apply_policy(await MCPSessionManager.get_clients(user_id, db), policy)


def _tool_map(client) -> dict:
    return {t.name: t for t in (client._tools or [])}


def build_mcp_catalog_prompt(clients: dict, max_tools: int = 150) -> str:
    """시스템 프롬프트용 MCP 도구 목록 (이름 + 한 줄 설명만). 머리말은 prompts/mcp_catalog.md."""
    if not clients:
        return ""
    lines = []
    count = 0
    for server, client in clients.items():
        lines.append(f"- server `{server}`:")
        for t in client._tools or []:
            if count >= max_tools:
                lines.append("  - ... (more tools: use load_mcp_tool with only `server` to list them)")
                break
            desc = " ".join((t.description or "").split())[:100]
            lines.append(f"  - {t.name}: {desc}" if desc else f"  - {t.name}")
            count += 1
    return "\n" + render("mcp_catalog", tools="\n".join(lines))


class _AsyncTool(BaseTool):
    user_id: str = ""
    mcp_policy: Optional[dict] = None  # 커스텀 에이전트의 MCP 허용 정책 (None 이면 제한 없음)

    def _run(self, *args, **kwargs) -> str:
        return "This tool supports async execution only"


# ── load_mcp_tool ────────────────────────────────────────────────────────────
class LoadMcpToolInput(BaseModel):
    server: Optional[str] = Field(default=None, description="MCP server name. Omit to list all servers and tools")
    tool: Optional[str] = Field(default=None, description="Tool name. Omit to list the tools of the server")


class LoadMcpToolTool(_AsyncTool):
    name: str = "load_mcp_tool"
    description: str = (
        "Inspect an external MCP tool before calling it: returns its description, input schema (arguments) and "
        "output format. Omit `tool` to list a server's tools, omit both to list every server."
    )
    args_schema: type[BaseModel] = LoadMcpToolInput

    async def _arun(self, server: Optional[str] = None, tool: Optional[str] = None) -> str:
        clients = await _clients(self.user_id, self.mcp_policy)
        if not clients:
            return "No MCP servers are connected."
        if not server:
            return json.dumps(
                {s: [{"name": t.name, "description": (t.description or "")[:200]} for t in c._tools or []]
                 for s, c in clients.items()},
                ensure_ascii=False,
            )
        client = clients.get(server)
        if not client:
            return f"Error: unknown MCP server '{server}'. Connected servers: {', '.join(clients)}"
        tools = _tool_map(client)
        if not tool:
            return json.dumps(
                [{"name": t.name, "description": (t.description or "")[:300]} for t in tools.values()],
                ensure_ascii=False,
            )
        t = tools.get(tool)
        if not t:
            return f"Error: unknown tool '{tool}' on server '{server}'. Tools: {', '.join(tools)}"
        out_schema = getattr(t, "outputSchema", None)
        info: dict[str, Any] = {
            "server": server,
            "tool": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema or {"type": "object", "properties": {}},
            "output": (
                {"schema": out_schema}
                if out_schema
                else {"format": "text (concatenated text content; often JSON - parse it if it starts with { or [)"}
            ),
            "usage": f'call_mcp_tool(server="{server}", tool="{t.name}", arguments={{...}})',
        }
        return _truncate(json.dumps(info, ensure_ascii=False))


# ── call_mcp_tool ────────────────────────────────────────────────────────────
class CallMcpToolInput(BaseModel):
    server: str = Field(description="MCP server name")
    tool: str = Field(description="Tool name on that server")
    arguments: dict = Field(default_factory=dict, description="Tool arguments matching the input schema from load_mcp_tool")


class CallMcpToolTool(_AsyncTool):
    name: str = "call_mcp_tool"
    description: str = (
        "Call one tool of an MCP server once and return its result text. Check the arguments with load_mcp_tool first. "
        "For chaining several calls or processing large results use run_mcp_code instead."
    )
    args_schema: type[BaseModel] = CallMcpToolInput

    async def _arun(self, server: str, tool: str, arguments: Optional[dict] = None) -> str:
        clients = await _clients(self.user_id, self.mcp_policy)
        client = clients.get(server)
        if not client:
            return f"[MCP Error] unknown MCP server '{server}'. Connected servers: {', '.join(clients) or '(none)'}"
        if tool not in _tool_map(client):
            return f"[MCP Error] unknown tool '{tool}' on server '{server}'. Tools: {', '.join(_tool_map(client))}"
        result = await client.call_tool(tool, arguments or {})
        if len(result.encode("utf-8")) > MAX_RPC_RESULT_BYTES:
            result = result.encode("utf-8")[:MAX_RPC_RESULT_BYTES].decode("utf-8", errors="ignore")
        return _truncate(result)


# ── run_mcp_code ─────────────────────────────────────────────────────────────
class RunMcpCodeInput(BaseModel):
    code: str = Field(
        description=(
            "Python code run in the sandbox. Use the preloaded `mcp` object: "
            "mcp.call(server, tool, **args) -> str, mcp.call_json(server, tool, **args) -> parsed JSON, "
            "mcp.tools(server=None) -> list. Loop/filter/aggregate in code and print() only the final summary."
        )
    )
    timeout: int = Field(default=120, description="Timeout in seconds (default 120, max 600)")


class RunMcpCodeTool(_AsyncTool):
    name: str = "run_mcp_code"
    description: str = (
        "Run Python code that chains multiple MCP tool calls or analyzes/aggregates large MCP results, so that raw data "
        "never fills the conversation. Inside the code use `mcp.call(server, tool, **args)` / `mcp.call_json(...)`. "
        "Only what the code print()s is returned. Check argument formats with load_mcp_tool first."
    )
    args_schema: type[BaseModel] = RunMcpCodeInput

    async def _arun(self, code: str, timeout: int = 120) -> str:
        from app.services.sandbox_service import sandbox_manager
        from app.tools.workspace_tools import _container

        clients = await _clients(self.user_id, self.mcp_policy)
        if not clients:
            return "No MCP servers are connected."
        t = min(max(timeout, 5), 600)

        async def handler(req: dict) -> dict:
            op = req.get("op")
            if op == "list":
                want = req.get("server")
                return {"result": [
                    {"server": s, "name": tl.name, "description": (tl.description or "")[:200]}
                    for s, c in clients.items() if not want or s == want for tl in c._tools or []
                ]}
            client = clients.get(req.get("server"))
            if not client:
                return {"error": f"unknown MCP server '{req.get('server')}'. Connected: {', '.join(clients)}"}
            name = req.get("tool")
            if name not in _tool_map(client):
                return {"error": f"unknown tool '{name}' on '{req.get('server')}'. Tools: {', '.join(_tool_map(client))}"}
            result = await client.call_tool(name, req.get("arguments") or {})
            if result.startswith("[MCP Error]"):
                return {"error": result}
            return {"result": result.encode("utf-8")[:MAX_RPC_RESULT_BYTES].decode("utf-8", errors="ignore")}

        try:
            cid = await _container(self.user_id)
            import uuid

            code_path = f"/tmp/_mcp_code_{uuid.uuid4().hex[:8]}.py"
            await sandbox_manager.write_file(cid, RUNNER_PATH, RUNNER_SOURCE.encode("utf-8"))
            await sandbox_manager.write_file(cid, code_path, code.encode("utf-8"))
            cmd = ["bash", "-c", f"timeout -k 3 {t} python3 -u {RUNNER_PATH} {shlex.quote(code_path)}; rc=$?; rm -f {shlex.quote(code_path)}; exit $rc"]
            exit_code, out, err, calls = await sandbox_manager.exec_with_rpc(
                cid, cmd, handler, timeout=t + 10, rpc_prefix=RPC_PREFIX
            )
            parts = []
            if out:
                parts.append(f"STDOUT:\n{_truncate(out.rstrip())}")
            if err:
                parts.append(f"STDERR:\n{_truncate(err.rstrip(), 8000)}")
            parts.append(f"Exit code: {exit_code}" + (f" (timed out after {t}s)" if exit_code == 124 else "") + f" | MCP calls: {calls}")
            return "\n".join(parts)
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

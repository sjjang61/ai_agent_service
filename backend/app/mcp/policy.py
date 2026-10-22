"""에이전트별 MCP 사용 정책: 어떤 서버·도구를 쓸 수 있는지 걸러낸다.

policy: None(제한 없음) | {server_name: None(모든 도구) | set(허용 도구 이름)}. 빈 dict 는 MCP 사용 안 함.
"""
import copy
from typing import Dict, Optional, Set

from app.schemas.agent import McpConfig

Policy = Optional[Dict[str, Optional[Set[str]]]]


def policy_from_config(cfg: McpConfig) -> Policy:
    if cfg.mode == "all":
        return None
    if cfg.mode == "none":
        return {}
    return {s.name: (set(s.allowed_tools) if s.allowed_tools is not None else None) for s in cfg.servers}


def apply_policy(clients: dict, policy: Policy) -> dict:
    """연결된 클라이언트 {서버명: MCPClient} 에서 허용된 서버·도구만 남긴 복사본을 돌려준다.
    클라이언트는 세션을 공유하는 얕은 복사본이며 _tools 만 줄어든다."""
    if policy is None:
        return clients
    out = {}
    for name, client in clients.items():
        if name not in policy:
            continue
        allowed = policy[name]
        if allowed is None:
            out[name] = client
            continue
        view = copy.copy(client)
        view._tools = [t for t in (client._tools or []) if t.name in allowed]
        out[name] = view
    return out

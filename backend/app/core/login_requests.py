"""브라우저 에이전트가 '사용자의 로그인이 필요하다'고 요청했을 때 완료를 기다리는 레지스트리.
form_ask_user(core/forms.py)와 같은 방식이다. 단일 프로세스(in-memory) 기준.
화면은 GET /api/browser/login-request 를 폴링해 요청을 보고, 사용자가 로그인을 끝내면 POST .../done 으로 알린다."""
import asyncio
import time
from typing import Optional


class _Pending:
    def __init__(self, user_id: str, info: dict, future: asyncio.Future):
        self.user_id, self.info, self.future = user_id, info, future
        self.created = time.time()


class PendingLogins:
    _pending: dict[str, _Pending] = {}

    @classmethod
    async def ask(cls, conversation_id: str, user_id: str, info: dict, timeout: float) -> dict:
        """반환: {"done": True} | {"cancelled": True} | {"timeout": True}"""
        old = cls._pending.pop(conversation_id, None)
        if old and not old.future.done():
            old.future.set_result({"cancelled": True})
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        cls._pending[conversation_id] = _Pending(user_id, info, fut)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return {"timeout": True}
        finally:
            cur = cls._pending.get(conversation_id)
            if cur and cur.future is fut:
                cls._pending.pop(conversation_id, None)

    @classmethod
    def get(cls, conversation_id: str, user_id: str) -> Optional[dict]:
        p = cls._pending.get(conversation_id)
        if not p or p.user_id != user_id or p.future.done():
            return None
        return p.info

    @classmethod
    def resolve(cls, conversation_id: str, user_id: str, cancelled: bool = False) -> bool:
        p = cls._pending.get(conversation_id)
        if not p or p.user_id != user_id or p.future.done():
            return False
        p.future.set_result({"cancelled": True} if cancelled else {"done": True})
        return True

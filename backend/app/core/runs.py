"""에이전트 실행을 취소할 수 있게 감싸는 레지스트리.

오케스트레이터 실행(LLM 호출, 도구 실행)을 별도 asyncio 태스크로 돌리고 이벤트를 큐로 넘겨받는다.
취소 API 가 그 태스크를 cancel 하면 진행 중인 await 지점(LLM 응답 대기, 도구 대기 등)에 CancelledError 가 전달된다.
대화(conversation)당 동시에 하나의 실행만 허용한다. 단일 프로세스(in-memory) 기준이다.
"""
import asyncio
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

_DONE = object()
_CANCELLED = object()


class _Run:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.task: "asyncio.Task" = None  # type: ignore[assignment]
        # 취소 요청 여부. Agno 같은 프레임워크는 CancelledError 를 내부에서 처리해 스트림을 "정상 종료"시키므로
        # 예외 전파만으로는 취소를 알 수 없다.
        self.cancel_requested = False


class RunRegistry:
    _runs: dict[str, _Run] = {}

    @classmethod
    def is_running(cls, conversation_id: str) -> bool:
        run = cls._runs.get(conversation_id)
        return bool(run and not run.task.done())

    @classmethod
    def cancel(cls, conversation_id: str, user_id: str) -> bool:
        """실행 중인 에이전트를 취소한다. 실행 중인 것이 없거나 다른 사용자의 것이면 False."""
        run = cls._runs.get(conversation_id)
        if not run or run.user_id != user_id or run.task.done():
            return False
        run.cancel_requested = True
        run.task.cancel()
        return True


async def cancellable_events(
    conversation_id: str, user_id: str, source: AsyncIterator[dict]
) -> AsyncIterator[dict]:
    """source(에이전트 이벤트 스트림)를 취소 가능한 태스크로 실행하며 이벤트를 전달한다.

    취소되면 {"type": "cancelled"} 이벤트를 하나 내보내고 끝난다.
    소비자(HTTP 연결)가 먼저 끊겨도 finally 에서 실행 태스크를 함께 취소한다.
    """
    queue: asyncio.Queue = asyncio.Queue()
    run = _Run(user_id)

    async def pump():
        try:
            async for event in source:
                await queue.put(event)
            # 취소를 요청했는데 스트림이 정상 종료됐다면(프레임워크가 취소를 삼킨 경우) 취소로 처리한다
            await queue.put(_CANCELLED if run.cancel_requested else _DONE)
        except asyncio.CancelledError:
            await queue.put(_CANCELLED)  # 취소는 정상 종료로 처리하고 소비자에게 알린다
        except Exception as e:  # noqa: BLE001
            await queue.put(e)
        finally:
            aclose = getattr(source, "aclose", None)
            if aclose:
                try:
                    await aclose()
                except BaseException:  # noqa: BLE001
                    pass

    task = asyncio.create_task(pump())
    run.task = task
    RunRegistry._runs[conversation_id] = run
    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                return
            if item is _CANCELLED:
                yield {"type": "cancelled"}
                return
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        cur = RunRegistry._runs.get(conversation_id)
        if cur and cur.task is task:
            RunRegistry._runs.pop(conversation_id, None)
        if not task.done():
            task.cancel()  # 연결이 끊겼거나 소비자가 중단한 경우

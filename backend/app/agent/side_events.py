"""도구 안에서 돌아가는 하위 에이전트(예: 브라우저 에이전트)의 진행 이벤트를 화면 스트림에 끼워 넣는 통로.

Agno 가 내보내는 이벤트에는 도구 '안'에서 일어난 일이 없으므로, 도구가 emit() 으로 이벤트를 넣으면
stream_team 이 팀 이벤트와 도착 순서대로 합쳐서 같은 스트림(= 저장되는 작업 내역)으로 내보낸다.
대화방(session_id) 단위이고, 열린 통로가 없으면(예약 실행 등) emit 은 아무 일도 하지 않는다.
"""
import asyncio
import time
from contextlib import nullcontext
from typing import AsyncIterator, Awaitable, Callable, ContextManager, Optional

_queues: dict[str, asyncio.Queue] = {}


def open_channel(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    return q


def close_channel(session_id: str, q: asyncio.Queue) -> None:
    if _queues.get(session_id) is q:
        _queues.pop(session_id, None)


def emit(session_id: str, event: dict) -> None:
    q = _queues.get(session_id)
    if q is not None and session_id:
        event.setdefault("ts", int(time.time() * 1000))  # 작업 시간 계산용 (이 이벤트가 실제로 일어난 시각, ms)
        q.put_nowait(event)


async def merge_stream(agen: AsyncIterator, q: asyncio.Queue, ctx: Optional[Callable[[], ContextManager]] = None) -> AsyncIterator[tuple[str, object]]:
    """스트리밍 이터레이터의 이벤트와 통로 이벤트를 도착 순서대로 ("team", ev) / ("side", ev) 로 내보낸다.

    이터레이터는 **하나의 태스크 안에서** 끝까지 돌린다(pump). 호출마다 새 태스크로 한 걸음씩 돌리면 그 안에서 시작한 트레이스 스팬의
    컨텍스트가 다음 걸음에 이어지지 않아 하위 스팬이 부모와 끊어진다. ctx 는 그 태스크 안에서 여는 컨텍스트(예: 모니터링의 대화 id 부여)다.
    """
    out: asyncio.Queue = asyncio.Queue()
    END = object()

    async def pump() -> None:
        try:
            with (ctx() if ctx else nullcontext()):
                async for ev in agen:
                    await out.put(("team", ev))
            await out.put((END, None))
        except BaseException as e:  # noqa: BLE001  취소 포함: 소비자에게 같은 예외를 다시 올린다
            await out.put(("exc", e))
            if isinstance(e, asyncio.CancelledError):
                raise

    pump_task = asyncio.ensure_future(pump())
    from_team: asyncio.Future = asyncio.ensure_future(out.get())
    from_side: asyncio.Future = asyncio.ensure_future(q.get())
    try:
        while True:
            done, _ = await asyncio.wait({from_team, from_side}, return_when=asyncio.FIRST_COMPLETED)
            if from_side in done:
                yield "side", from_side.result()
                from_side = asyncio.ensure_future(q.get())
            if from_team in done:
                kind, payload = from_team.result()
                if kind is END:
                    break
                if kind == "exc":
                    raise payload  # type: ignore[misc]
                yield "team", payload
                from_team = asyncio.ensure_future(out.get())
        while not q.empty():
            yield "side", q.get_nowait()
    finally:
        for f in (from_team, from_side, pump_task):
            if not f.done():
                f.cancel()


async def run_with_side(coro: Awaitable, q: asyncio.Queue, ctx: Optional[Callable[[], ContextManager]] = None) -> AsyncIterator[tuple[str, object]]:
    """스트리밍이 아닌 실행: 완료를 기다리는 동안 통로 이벤트를 내보내고, 끝나면 ("done", 결과) 를 내보낸다. ctx 는 실행 태스크 안에서 여는 컨텍스트."""

    async def run():
        with (ctx() if ctx else nullcontext()):
            return await coro

    task = asyncio.ensure_future(run())
    try:
        while not task.done():
            try:
                yield "side", await asyncio.wait_for(q.get(), 0.2)
            except asyncio.TimeoutError:
                pass
        while not q.empty():
            yield "side", q.get_nowait()
        yield "done", task.result()
    finally:
        if not task.done():
            task.cancel()

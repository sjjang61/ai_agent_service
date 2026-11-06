import asyncio
import json

from app.agent.orchestrator import with_plan_finish
from app.core.runs import RunRegistry
from app.tools.interaction_tools import _todo_store, finish_plan, seed_todos


async def _gen(events):
    for e in events:
        yield e


def _run(conv, events):
    async def go():
        return [e async for e in with_plan_finish(conv, _gen(events))]

    return asyncio.run(go())


def test_finish_plan_completes_remaining_steps():
    seed_todos("c-fin", ["a", "b", "c"])
    out = json.loads(finish_plan("c-fin"))
    assert out["progress"] == "3/3" and all(t["status"] == "completed" for t in out["todos"])
    assert finish_plan("c-fin") is None          # 이미 끝났으면 아무것도 하지 않는다
    assert finish_plan("missing") is None


def test_normal_answer_finishes_plan():
    seed_todos("c-ok", ["a", "b"])
    evs = _run("c-ok", [{"type": "token", "content": "완료"}])
    assert [e["type"] for e in evs] == ["token", "tool_call", "tool_result"]
    assert json.loads(evs[-1]["output"])["progress"] == "2/2"


def test_error_or_no_answer_keeps_plan():
    seed_todos("c-err", ["a", "b"])
    assert [e["type"] for e in _run("c-err", [{"type": "token", "content": "x"}, {"type": "error", "message": "boom"}])] == ["token", "error"]
    assert [t["status"] for t in _todo_store["c-err"]] == ["in_progress", "pending"]
    seed_todos("c-none", ["a"])
    assert _run("c-none", [{"type": "tool_call", "tool": "x"}]) == [{"type": "tool_call", "tool": "x"}]


def test_cancel_requested_keeps_plan(monkeypatch):
    seed_todos("c-cancel", ["a", "b"])
    monkeypatch.setattr(RunRegistry, "cancel_requested", classmethod(lambda cls, cid: True))
    assert [e["type"] for e in _run("c-cancel", [{"type": "token", "content": "x"}])] == ["token"]
    assert _todo_store["c-cancel"][0]["status"] == "in_progress"


def test_no_plan_adds_nothing():
    assert [e["type"] for e in _run("c-noplan", [{"type": "token", "content": "x"}])] == ["token"]


def test_run_registry_is_running_by_user():
    async def go():
        gate = asyncio.Event()

        async def src():
            await gate.wait()
            yield {"type": "token", "content": "x"}

        from app.core.runs import cancellable_events

        agen = cancellable_events("c-run", "u1", src())
        task = asyncio.create_task(agen.__anext__())
        await asyncio.sleep(0.05)
        assert RunRegistry.is_running("c-run") and RunRegistry.is_running("c-run", "u1")
        assert not RunRegistry.is_running("c-run", "other")      # 남의 실행은 보이지 않는다
        gate.set()
        await task
        await agen.aclose()
        await asyncio.sleep(0.05)
        assert not RunRegistry.is_running("c-run", "u1")

    asyncio.run(go())

"""Function 트리거: 예약(선점·유예·자동 중지·고정 버전)과 웹훅(해시 저장·재발급·404 통일·한도) — 서비스와 API"""
import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.function import FunctionRun, FunctionTrigger
from app.services import function_service as fsvc
from app.services import function_trigger_service as tsvc
from app.services.function_service import FunctionError
from tests.unit.test_function_service import U1, U2, env, make, zip_of  # noqa: F401  (fixtures)


async def runs_of(env, fn_id=None):
    q = select(FunctionRun)
    if fn_id:
        q = q.where(FunctionRun.function_id == fn_id)
    return list((await env.db.execute(q.order_by(FunctionRun.queued_at))).scalars().all())


# ── 예약 ──────────────────────────────────────────────────────
async def test_create_schedule_validates_and_computes_next_run(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "매일", None, "daily", schedule_time="09:00", timezone_name="Asia/Seoul")
    assert t.kind == "schedule" and t.ref == "latest" and t.enabled and t.next_run_at > tsvc._now()
    assert tsvc.trigger_dict(t)["description"].startswith("매일 09:00")
    bad = [("hourly", {}), ("interval", {"interval_hours": 0}), ("weekly", {"schedule_time": "09:00", "weekdays": []}), ("daily", {"schedule_time": "25:99"}),
           ("monthly", {"schedule_time": "09:00", "day_of_month": 40}), ("once", {"run_at": tsvc._now() - timedelta(hours=1)})]
    for typ, spec in bad:
        with pytest.raises(FunctionError) as e:
            await tsvc.create_schedule(env.db, U1, fn.id, "x", None, typ, **spec)
        assert e.value.status == 400, typ
    with pytest.raises(FunctionError) as e:
        await tsvc.create_schedule(env.db, U1, fn.id, "x", "nope-alias", "daily", schedule_time="09:00")
    assert e.value.status == 404  # 없는 별칭은 만들 때 거부한다


async def test_trigger_count_cap(env, monkeypatch):
    monkeypatch.setattr(settings, "FUNCTION_TRIGGERS_MAX_PER_USER", 2)
    fn, _ = await make(env)
    await tsvc.create_webhook(env.db, U1, fn.id, "a", None)
    await tsvc.create_webhook(env.db, U1, fn.id, "b", None)
    with pytest.raises(FunctionError) as e:
        await tsvc.create_webhook(env.db, U1, fn.id, "c", None)
    assert e.value.status == 400


async def test_due_schedule_fires_once_with_pinned_version_and_advances(env):
    fn, _ = await make(env)
    await fsvc.add_version(env.db, U1, fn.id, zip_of("def handler(e, c): return 2\n"), store=env.store)
    await fsvc.set_alias(env.db, U1.id, fn.id, "prod", 1)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", "prod", "interval", interval_hours=2)
    first_due = t.next_run_at
    now = first_due + timedelta(seconds=5)
    assert await tsvc.fire_due_schedules(env.db, now) == 1
    assert await tsvc.fire_due_schedules(env.db, now) == 0  # 같은 시각에 다시 돌아도 중복 실행하지 않는다
    (run,) = await runs_of(env, fn.id)
    assert (run.trigger, run.version, run.status) == ("schedule", 1, "queued")  # 별칭 prod 가 가리키는 v1 (latest 는 v2)
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert t.next_run_at == now + timedelta(hours=2)  # 반복 간격만큼 뒤로 넘어간다
    assert t.last_run_id == run.id and t.last_status == "queued"


async def test_once_schedule_disables_after_firing(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "once", None, "once", run_at=tsvc._now() + timedelta(minutes=5))
    assert await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(seconds=1)) == 1
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert t.enabled is False and t.next_run_at is None


async def test_missed_schedule_beyond_grace_is_skipped(env, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_MISFIRE_GRACE_SECONDS", 600)
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    assert await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(hours=3)) == 0  # 서버가 3시간 멈춰 있었다
    assert await runs_of(env) == []
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert "건너뜀" in t.last_status and t.next_run_at is not None and t.enabled


async def test_concurrent_firing_claims_each_due_schedule_once(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    now = t.next_run_at + timedelta(seconds=1)
    async with env.maker() as other:
        a, b = await asyncio.gather(tsvc.fire_due_schedules(env.db, now), tsvc.fire_due_schedules(other, now))
    assert a + b == 1 and len(await runs_of(env)) == 1


async def test_auto_disable_after_consecutive_failures(env, monkeypatch):
    monkeypatch.setattr(settings, "SCHEDULER_MAX_CONSECUTIVE_FAILURES", 2)
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    now = t.next_run_at
    for i in range(3):
        fired = await tsvc.fire_due_schedules(env.db, now + timedelta(seconds=1))
        for r in await runs_of(env):  # 방금 만든 실행이 실패로 끝났다고 가정
            r.status, r.finished_at = "failed", tsvc._now()
        await env.db.commit()
        t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
        if not t.enabled:
            break
        now = t.next_run_at
    assert t.enabled is False and "자동으로 멈췄습니다" in t.last_status and i == 2  # 2번 연속 실패를 본 세 번째 회차에서 멈춘다


async def test_success_resets_failure_counter(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    t.consecutive_failures = 2
    await env.db.commit()
    await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(seconds=1))
    for r in await runs_of(env):
        r.status = "succeeded"
    await env.db.commit()
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(seconds=1))
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert t.consecutive_failures == 0 and t.enabled


async def test_disabled_schedule_does_not_fire_and_reenable_recomputes(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    due = t.next_run_at
    await tsvc.set_enabled(env.db, U1.id, t.id, False)
    assert await tsvc.fire_due_schedules(env.db, due + timedelta(hours=1)) == 0
    t2 = await tsvc.set_enabled(env.db, U1.id, t.id, True)
    assert t2.enabled and t2.next_run_at > tsvc._now()


async def test_quota_rejection_is_recorded_not_raised(env, monkeypatch):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    monkeypatch.setattr(settings, "FUNCTION_RUNS_PER_DAY_PER_USER", 0)
    assert await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(seconds=1)) == 0
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert "실행하지 못함" in t.last_status and t.consecutive_failures == 1


# ── 웹훅 ──────────────────────────────────────────────────────
async def test_webhook_token_is_returned_once_and_only_its_hash_is_stored(env):
    fn, _ = await make(env)
    t, token = await tsvc.create_webhook(env.db, U1, fn.id, "hook", "latest")
    assert len(token) >= 40 and t.token_hash == tsvc.hash_token(token) and token not in json.dumps(tsvc.trigger_dict(t))
    assert tsvc.trigger_dict(t, token)["path"] == f"/api/fn-hooks/{token}"
    run = await tsvc.fire_webhook(env.db, token, {"x": 1})
    assert (run.trigger, run.status) == ("webhook", "queued") and json.loads(run.input) == {"x": 1}
    assert (await env.db.get(FunctionTrigger, t.id, populate_existing=True)).last_called_at is not None


async def test_webhook_unknown_disabled_regenerated_and_blocked_owner_all_404(env, monkeypatch):
    fn, _ = await make(env)
    t, token = await tsvc.create_webhook(env.db, U1, fn.id, "hook", None)
    for bad in ("", "nope", token + "x", token[:-1]):
        with pytest.raises(FunctionError) as e:
            await tsvc.fire_webhook(env.db, bad, {})
        assert e.value.status == 404
    _, new = await tsvc.regenerate_webhook(env.db, U1.id, t.id)
    assert new != token
    with pytest.raises(FunctionError) as e:
        await tsvc.fire_webhook(env.db, token, {})  # 이전 토큰은 즉시 무효
    assert e.value.status == 404
    await tsvc.fire_webhook(env.db, new, {})
    await tsvc.set_enabled(env.db, U1.id, t.id, False)
    with pytest.raises(FunctionError) as e:
        await tsvc.fire_webhook(env.db, new, {})
    assert e.value.status == 404
    await tsvc.set_enabled(env.db, U1.id, t.id, True)
    await fsvc.set_disabled(env.db, fn.id, True, "남용")  # 관리자 중지: 토큰 보유자에게는 이유를 알리지 않는다
    with pytest.raises(FunctionError) as e:
        await tsvc.fire_webhook(env.db, new, {})
    assert e.value.status == 404 and "남용" not in e.value.message
    await fsvc.set_disabled(env.db, fn.id, False)
    monkeypatch.setattr(settings, "FUNCTION_ALLOWED_EMAILS", "someone-else@x.com")  # 소유자의 사용 권한이 사라졌다
    with pytest.raises(FunctionError) as e:
        await tsvc.fire_webhook(env.db, new, {})
    assert e.value.status == 404


async def test_webhook_respects_quotas(env, monkeypatch):
    fn, _ = await make(env)
    _, token = await tsvc.create_webhook(env.db, U1, fn.id, "hook", None)
    monkeypatch.setattr(settings, "FUNCTION_RUNS_PER_DAY_PER_USER", 1)
    await tsvc.fire_webhook(env.db, token, {})
    with pytest.raises(FunctionError) as e:
        await tsvc.fire_webhook(env.db, token, {})
    assert e.value.status == 429  # 한도는 숨기지 않는다


async def test_other_user_cannot_touch_my_triggers(env):
    fn, _ = await make(env)
    t, _ = await tsvc.create_webhook(env.db, U1, fn.id, "hook", None)
    for coro in (tsvc.get_trigger(env.db, U2.id, t.id), tsvc.set_enabled(env.db, U2.id, t.id, False), tsvc.delete_trigger(env.db, U2.id, t.id),
                 tsvc.regenerate_webhook(env.db, U2.id, t.id), tsvc.create_webhook(env.db, U2, fn.id, "x", None)):
        with pytest.raises(FunctionError) as e:
            await coro
        assert e.value.status == 404
    assert await tsvc.list_triggers(env.db, U2.id) == []


async def test_regenerate_rejects_schedule_triggers(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    with pytest.raises(FunctionError) as e:
        await tsvc.regenerate_webhook(env.db, U1.id, t.id)
    assert e.value.status == 400


async def test_listing_shows_the_current_status_of_the_last_run_not_the_stale_queued_text(env):
    fn, _ = await make(env)
    t = await tsvc.create_schedule(env.db, U1, fn.id, "n", None, "interval", interval_hours=1)
    await tsvc.fire_due_schedules(env.db, t.next_run_at + timedelta(seconds=1))
    t = await env.db.get(FunctionTrigger, t.id, populate_existing=True)
    assert t.last_status == "queued"  # 행에는 큐에 넣을 때의 값이 남는다
    (run,) = await runs_of(env)
    run.status = "succeeded"
    await env.db.commit()
    st = await tsvc.run_statuses(env.db, [t])
    assert tsvc.trigger_dict(t, run_status=st[t.last_run_id])["last_status"] == "마지막 실행 성공"
    assert tsvc.trigger_dict(t)["last_status"] == "queued" and await tsvc.run_statuses(env.db, []) == {}

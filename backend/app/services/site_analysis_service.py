"""웹사이트 분석: 브라우저 에이전트가 사이트를 직접 써 보고 '사이트 요령' 초안을 만들고(analyze), 그 초안으로 시나리오를 다시 수행해
쓸 만한지 확인한다(verify). 실행은 백그라운드 태스크로 돌고, 진행 단계와 결과는 DB 행에 쌓아 화면이 주기적으로 읽는다.

읽기 전용: 로그인·장바구니·예약·결제 같은 쓰기 동작은 승인 화면이 없으므로 정책상 실행되지 않고(browser_policy), 결제 직전 중단 가드도 그대로 적용된다.
"""
import asyncio
import json
import logging
import re
import time
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import side_events, site_spec, site_tips
from app.agent.prompts import render
from app.config import settings
from app.models.site_profile import SiteAnalysisRun
from app.services import browser_policy

logger = logging.getLogger(__name__)

MODES = ("analyze", "verify")
STEP_STATUSES = ("reached", "failed", "skipped")  # 검증에서 에이전트가 보고하는 단계별 결과
MAX_STEPS_KEPT = 150
MAX_LOOP_BLOCKS_TO_PASS = 2  # 같은 동작을 반복해 막힌 횟수가 이보다 많으면 요령이 쓸 만하지 않은 것으로 본다
FLUSH_INTERVAL = 1.0
DEFAULT_SCENARIO = "이 분야의 표준 진행 단계를 아래 입력값으로 처음부터 끝까지 수행한다 (상태를 바꾸는 단계는 제외)"

_tasks: dict[str, asyncio.Task] = {}


class AnalysisError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


# ── 순수 함수: 입력 정리, 결과 해석 ────────────────────────────
def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if raw and "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or len(raw) > 500:
        raise AnalysisError(400, "시작 주소가 올바르지 않습니다 (예: https://www.danawa.com)")
    return raw


def host_domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def json_after_tag(text: str, tag: str):
    """답변에서 `<태그>` 바로 뒤의 JSON 객체를 꺼낸다. 닫는 태그는 보지 않는다 (모델이 `</태그>` 를 `}태그>` 처럼 틀리게 닫거나 빠뜨려도 읽힌다).
    (객체, 오류 설명) — 태그가 없으면 (None, 'missing'), JSON 이 아니면 (None, 오류 설명)."""
    m = re.search(rf"<{tag}>\s*(?:```(?:json)?\s*)?", text or "")
    if not m:
        return None, "missing"
    try:
        obj, _ = json.JSONDecoder().raw_decode((text or "")[m.end():])
    except json.JSONDecodeError as e:
        return None, e.msg
    return obj, ""


def parse_structure(text: str) -> tuple[dict, str]:
    """답변의 <구조>{사이트 spec JSON}</구조> 를 (정리된 spec, 오류 설명)으로. 없거나 잘못되면 ({}, 이유)."""
    obj, err = json_after_tag(text, "구조")
    if obj is None:
        return {}, "<구조> 블록이 없습니다" if err == "missing" else f"<구조> 가 JSON 이 아닙니다 ({err})"
    try:
        return site_spec.clean_site(obj), ""
    except site_spec.SpecError as e:
        return {}, f"<구조> 검증 실패: {e}"


def parse_draft(text: str) -> tuple[str, str]:
    """에이전트 답변에서 (요령 본문, 분석 메모)를 꺼낸다. <요령> 태그가 없으면 본문은 빈 문자열이다 (구조만 있는 답변도 있다)."""
    m = re.search(r"<요령>(.*?)</요령>", text or "", re.S)
    if not m:
        return "", re.sub(r"<구조>.*?</구조>", "", text or "", flags=re.S).strip()
    after = re.sub(r"<구조>.*?</구조>", "", text[m.end():], flags=re.S).strip()
    notes = after or re.sub(r"<구조>.*?</구조>", "", text[: m.start()], flags=re.S).strip()  # 요령 뒤의 분석 메모 (없으면 앞의 말)
    notes = re.sub(r"^\s*분석 메모\s*[:：]?\s*", "", notes)
    return m.group(1).strip(), notes


def parse_verdict(text: str) -> Optional[dict]:
    data, _ = json_after_tag(text, "검증")
    if not isinstance(data, dict) or not isinstance(data.get("success"), bool):
        return None
    issues = [str(i)[:300] for i in data.get("issues", []) if str(i).strip()] if isinstance(data.get("issues"), list) else []
    steps = []
    for st in data.get("steps", []) if isinstance(data.get("steps"), list) else []:
        if isinstance(st, dict) and str(st.get("key") or "").strip():
            status = str(st.get("status") or "").strip().lower()
            steps.append({"key": str(st["key"]).strip().lower()[:30], "status": status if status in STEP_STATUSES else "failed", "note": str(st.get("note") or "")[:300]})
    return {"success": data["success"], "summary": str(data.get("summary") or "")[:500], "issues": issues[:10], "steps": steps[:20]}


def evaluate_flow(vflow: list, reported: list, site_skips: Optional[set] = None) -> list:
    """분야의 표준 단계마다 검증 결과를 붙인다. 상태를 바꾸는 단계(write)는 읽기 전용 검증으로 시험할 수 없으므로 'untested', 보고되지 않은 단계는 'missing'.
    사이트 설명서가 '하지 않는 단계'로 표시한 단계(site_skips)는 도달하지 않아도 감점하지 않는다 ('excluded'). 그래도 도달했다고 보고하면 그대로 인정한다."""
    got = {r["key"]: r for r in reported}
    out = []
    for st in vflow:
        if st.get("write"):
            out.append({"key": st["key"], "title": st["title"], "write": True, "status": "untested", "note": "상태를 바꾸는 단계라 읽기 전용 검증에서는 시험하지 않습니다"})
        elif st["key"] in (site_skips or set()) and got.get(st["key"], {}).get("status") != "reached":
            note = got.get(st["key"], {}).get("note") or "이 사이트에서는 하지 않는 단계로 설명서에 표시되어 있어 시험하지 않았습니다"
            out.append({"key": st["key"], "title": st["title"], "write": False, "status": "excluded", "note": note})
        elif st["key"] in got:
            out.append({"key": st["key"], "title": st["title"], "write": False, "status": got[st["key"]]["status"], "note": got[st["key"]]["note"]})
        else:
            out.append({"key": st["key"], "title": st["title"], "write": False, "status": "missing", "note": "에이전트가 이 단계의 결과를 보고하지 않았습니다"})
    return out


def evaluate(verdict: Optional[dict], steps: list, loop_blocks: int, seconds: float, vflow: Optional[list] = None, site_skips: Optional[set] = None) -> dict:
    """재현 검증 결과: 에이전트가 성공을 보고했고, 분야의 읽기 단계가 모두 'reached' 이며, 같은 동작을 반복하다 막힌 일이 많지 않을 때만 통과로 본다.
    판정은 에이전트의 보고에 기대므로 사람이 마지막 화면(스크린샷)을 확인하는 보조 수단이다."""
    n = sum(1 for s in steps if s.get("action"))
    failed = sum(1 for s in steps if s.get("ok") is False)
    base = {"steps": n, "failed_steps": failed, "loop_blocks": loop_blocks, "seconds": round(seconds, 1)}
    if verdict is None:
        return {**base, "passed": False, "success": False, "flow": evaluate_flow(vflow or [], [], site_skips),
                "summary": "에이전트가 검증 결과를 보고하지 않았습니다 (단계 수 제한에 걸렸거나 도중에 멈췄을 수 있습니다)", "issues": []}
    issues = list(verdict["issues"])
    flow = evaluate_flow(vflow or [], verdict.get("steps", []), site_skips)
    bad = [f for f in flow if f["status"] in ("failed", "skipped", "missing")]
    passed = verdict["success"] and loop_blocks <= MAX_LOOP_BLOCKS_TO_PASS and not bad
    if verdict["success"] and loop_blocks > MAX_LOOP_BLOCKS_TO_PASS:
        issues.append(f"같은 동작을 반복하다 {loop_blocks}번 막혔습니다")
    if verdict["success"] and bad:
        issues.append("도달하지 못한 단계: " + ", ".join(f["title"] for f in bad))
    return {**base, "passed": passed, "success": verdict["success"], "summary": verdict["summary"], "issues": issues, "flow": flow}


def snap(steps: list) -> list:
    """저장용 복사본. 같은 dict 를 계속 고치면 SQLAlchemy 가 JSON 의 변화를 알아채지 못해 저장하지 않는다."""
    return [dict(s) for s in steps]


def fold_event(steps: list, ev: dict) -> bool:
    """브라우저 도구의 진행 이벤트를 단계 목록에 반영한다. 바뀌었으면 True."""
    if ev.get("tool") != "browser_action":
        return False
    cid = ev.get("call_id")
    if ev.get("type") == "tool_call":
        inp = ev.get("input") or {}
        if len(steps) < MAX_STEPS_KEPT:
            steps.append({"id": cid, "action": inp.get("action", ""), "desc": inp.get("desc") or inp.get("action", ""), "url": str(inp.get("url") or "")[:200],
                          "ok": None, "brief": "", "t0": ev.get("ts"), "t1": None})
        return True
    if ev.get("type") == "tool_result":
        for s in reversed(steps):
            if s["id"] == cid:
                s["ok"], s["brief"], s["t1"] = bool(ev.get("success", True)), str(ev.get("output") or "")[:200], ev.get("ts")
                return True
    return False


# ── 시작·조회·취소 ──────────────────────────────────────────
async def _running(db: AsyncSession, user_id: str) -> Optional[SiteAnalysisRun]:
    return (await db.execute(
        select(SiteAnalysisRun).where(SiteAnalysisRun.user_id == user_id, SiteAnalysisRun.status == "running").limit(1)
    )).scalar_one_or_none()


async def start(db: AsyncSession, user_id: str, data: dict) -> SiteAnalysisRun:
    mode = data.get("mode")
    if mode not in MODES:
        raise AnalysisError(400, "mode 는 analyze 또는 verify 여야 합니다")
    name = (data.get("name") or "").strip()
    if not name or len(name) > 100:
        raise AnalysisError(400, "사이트 이름은 1~100자로 입력하세요")
    url = normalize_url(data.get("start_url", ""))
    denied = browser_policy.domain_denied(url)
    if denied:
        raise AnalysisError(400, denied)
    vertical = (data.get("vertical") or "").strip().lower() or None
    vert = site_tips.vertical(vertical) if vertical else None
    if vertical and vert is None:
        raise AnalysisError(404, "분야를 찾을 수 없습니다")
    scenario = (data.get("scenario") or "").strip()
    if not scenario and vert is not None and vert.spec.get("flow"):
        scenario = DEFAULT_SCENARIO  # 분야의 표준 플로우를 샘플 입력값으로 수행한다
    if len(scenario) < 5 or len(scenario) > 1000:
        raise AnalysisError(400, "시나리오는 5~1000자로 입력하세요 (분야를 고르면 비워 둘 수 있습니다)")
    try:
        spec = site_spec.clean_site(data.get("draft_spec"))
    except site_spec.SpecError as e:
        raise AnalysisError(400, str(e))
    inputs = {str(k): str(v).strip()[:100] for k, v in (data.get("inputs") or {}).items() if isinstance(data.get("inputs"), dict) and str(v).strip()}
    draft = (data.get("draft_body") or "").strip()
    if mode == "verify" and not draft and not spec:
        raise AnalysisError(400, "검증할 요령 초안이 비어 있습니다")
    if len(draft) > 20000:
        raise AnalysisError(400, "요령이 너무 깁니다")
    clean = bool(data.get("clean_session"))
    if clean and data.get("captcha_handoff"):
        raise AnalysisError(400, "깨끗한 서버 브라우저에서는 캡차를 넘길 수 없습니다. 둘 중 하나만 선택하세요")
    if await _running(db, user_id) is not None:
        raise AnalysisError(409, "이미 실행 중인 분석이 있습니다. 끝나거나 중단된 뒤에 다시 시작하세요")
    run = SiteAnalysisRun(user_id=user_id, mode=mode, name=name, vertical=vertical, start_url=url, scenario=scenario, status="running",
                          steps=[], draft_body=draft or None, draft_spec=spec or None, inputs=inputs or None, captcha_handoff=bool(data.get("captcha_handoff")), clean_session=clean, base_run_id=(data.get("base_run_id") or None))
    db.add(run)
    await db.commit()
    await db.refresh(run)
    task = asyncio.create_task(_execute(run.id, current_body=(data.get("current_body") or "").strip()))
    _tasks[run.id] = task
    task.add_done_callback(lambda _t, rid=run.id: _tasks.pop(rid, None))
    return run


async def get_run(db: AsyncSession, user_id: str, run_id: str) -> SiteAnalysisRun:
    run = await db.get(SiteAnalysisRun, run_id)
    if run is None or run.user_id != user_id:
        raise AnalysisError(404, "실행 기록을 찾을 수 없습니다")
    return run


async def list_runs(db: AsyncSession, user_id: str, name: Optional[str] = None, limit: int = 10) -> list[SiteAnalysisRun]:
    q = select(SiteAnalysisRun).where(SiteAnalysisRun.user_id == user_id)
    if name:
        q = q.where(SiteAnalysisRun.name == name)
    return list((await db.execute(q.order_by(SiteAnalysisRun.created_at.desc()).limit(max(1, min(limit, 30))))).scalars().all())


async def cancel(db: AsyncSession, user_id: str, run_id: str) -> SiteAnalysisRun:
    run = await get_run(db, user_id, run_id)
    task = _tasks.get(run_id)
    if run.status == "running" and task is not None:
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), 5)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):  # noqa: BLE001
            pass
        await db.refresh(run)
    return run


async def mark_interrupted() -> None:
    """서버가 재시작되면 실행 중이던 분석은 이어지지 않으므로 실패로 닫는다."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(SiteAnalysisRun).where(SiteAnalysisRun.status == "running"))).scalars().all()
        for r in rows:
            r.status, r.error, r.finished_at = "failed", "서버가 다시 시작되어 중단되었습니다", datetime.now(timezone.utc)
        if rows:
            await db.commit()


# ── 실행 ────────────────────────────────────────────────────
def _blocks_for(run: SiteAnalysisRun) -> tuple[list[str], set]:
    """에이전트 지침에 붙일 분야 지침(과 검증이면 시험할 초안)과, 이미 안내한 것의 표시."""
    blocks: list[str] = []
    shown: set = {run.name}
    vert = site_tips.vertical(run.vertical) if run.vertical else None
    if vert is not None:
        blocks.append(vert.block())
        shown.add(f"@{vert.key}")
    for existing in site_tips.tips_for_url(run.start_url):
        shown.add(existing.name)  # 저장된 요령 (같은 도메인의 다른 분야 요령 포함)이 이번 실행에 끼어들지 않게 한다 (분석은 새로 보고, 검증은 초안만 시험한다)
    if run.mode == "verify":
        tip = site_tips.SiteTip(name=run.name, domains=(host_domain(run.start_url),), aliases=(), verified=date.today().isoformat(),
                                body=run.draft_body or "", vertical=run.vertical or "", spec=run.draft_spec or {})
        blocks.append(tip.block(hint=False))
    return blocks, shown


def _vspec(run: SiteAnalysisRun) -> dict:
    vert = site_tips.vertical(run.vertical) if run.vertical else None
    return (vert.spec if vert else None) or {}


def _flow_list(vspec: dict) -> str:
    return "\n".join(f"- {s['key']}: {s['title']}" + (" (상태를 바꾸는 단계: 실행하지 않고 '진행 방법'만 기록)" if s.get("write") else "") for s in vspec.get("flow", [])) or "(정의된 단계 없음)"


def _prompt(run: SiteAnalysisRun, current_body: str) -> str:
    vspec = _vspec(run)
    samples = site_spec.sample_text(vspec, run.inputs) or "(정의된 입력값 없음: 시나리오의 값을 쓰세요)"
    if run.mode == "analyze":
        vert = site_tips.vertical(run.vertical) if run.vertical else None
        text = render("site_analysis", name=run.name, vertical=vert.name if vert else "(분야 없음)", start_url=run.start_url, scenario=run.scenario,
                      checklist=(vert.checklist if vert and vert.checklist else "(체크리스트 없음: 주소 형식, 조건·정렬 적용 방법, 결과 화면 구조, 로그인·캡차, 멈출 지점을 확인하세요)"),
                      inputs=site_spec.render_vertical({"inputs": vspec.get("inputs", [])}) or "(정의된 입력값 없음)", samples=samples, flow=_flow_list(vspec),
                      current=current_body or "(없음)", current_spec=json.dumps(run.draft_spec, ensure_ascii=False, indent=1) if run.draft_spec else "(없음)")
    else:
        text = render("site_verify", name=run.name, start_url=run.start_url, scenario=run.scenario, samples=samples, flow=_flow_list(vspec))
    return f"{text}\n\n(시작 URL: {run.start_url})"


async def _execute(run_id: str, current_body: str = "") -> None:
    from agno.agent import Agent

    from app.agent.agno_engine import build_agno_model, to_agno_function
    from app.db.session import AsyncSessionLocal
    from app.tools import browser_tools as bt

    async with AsyncSessionLocal() as db:
        run = await db.get(SiteAnalysisRun, run_id)
        if run is None:
            return
        steps: list = []
        started = time.time()
        conv = f"siteanalysis:{run.id}"
        q = side_events.open_channel(conv)
        tool = None
        try:
            run.browser_run = uuid.uuid4().hex[:8]
            await db.commit()
            if run.clean_session:
                from app.services.local_browser import force_sandbox

                force_sandbox()  # 이 실행의 브라우저 작업은 내 앱 브라우저가 아니라 sandbox 로
                try:
                    await bt.browser_call(run.user_id, {"cmd": "close"}, timeout=15, use_profile=False)  # 이전 실행의 세션(쿠키·입력 기록)을 버리고 새로 시작한다
                except Exception:  # noqa: BLE001
                    pass  # 켜져 있던 브라우저가 없을 수도 있다
            elif settings.LOCAL_BROWSER_CDP_URL and run.user_id == settings.LOCAL_BROWSER_USER_ID:
                from app.services.local_browser import reset_if_new_turn

                await reset_if_new_turn(run.user_id)  # 남은 탭을 닫고 깨끗하게 시작
            bt.clear_handoff(run.user_id)
            blocks, shown = _blocks_for(run)
            clock = bt.WaitClock()
            tool = bt.BrowserActionTool(user_id=run.user_id, run_tag=run.browser_run, conversation_id=conv, login_enabled=False,
                                        clock=clock, tips_shown=shown, captcha_handoff=bool(run.captcha_handoff), ignore_site_block=True,
                                        use_profile=not run.clean_session)
            agent = Agent(
                name="SiteAnalyst" if run.mode == "analyze" else "SiteVerifier",
                model=build_agno_model(settings.LLM_TYPE, None),
                tools=[to_agno_function(tool)],
                tool_call_limit=settings.SITE_ANALYSIS_MAX_STEPS,
                instructions=bt.BROWSER_INSTRUCTIONS + blocks,
                compress_tool_results=True,
                compression_manager=bt._make_compression_manager(),
            )
            last_flush = 0.0
            text = ""
            async for kind, payload in side_events.run_with_side(
                bt.run_with_budget(agent.arun(_prompt(run, current_body)), settings.SITE_ANALYSIS_TIMEOUT_SECONDS, clock), q
            ):
                if kind == "side":
                    if fold_event(steps, payload) and time.time() - last_flush >= FLUSH_INTERVAL:
                        run.steps, last_flush = snap(steps), time.time()
                        await db.commit()
                else:
                    text = str(getattr(payload, "content", "") or "").strip()
            run.steps = snap(steps)
            run.answer = text[:15000] or None
            seconds = time.time() - started
            if run.mode == "analyze":
                body, notes = parse_draft(text)
                spec, spec_err = parse_structure(text)
                if spec or body:
                    run.draft_body, run.draft_spec, run.status = body, spec or None, "succeeded"
                    run.answer = (notes + (f"\n\n(구조 해석: {spec_err})" if spec_err else ""))[:15000] or None
                else:
                    run.status, run.error = "failed", f"에이전트가 <구조>·<요령> 형식으로 초안을 만들지 못했습니다 ({spec_err}). 답변 원문은 메모에 남깁니다"
            else:
                run.result = evaluate(parse_verdict(text), steps, tool._loop_blocks, seconds, _vspec(run).get("flow", []), site_spec.skipped_keys(run.draft_spec))
                run.status = "succeeded"
        except asyncio.CancelledError:
            run.steps, run.status, run.error = snap(steps), "cancelled", "사용자가 중단했습니다"
        except asyncio.TimeoutError:
            run.steps, run.status, run.error = snap(steps), "failed", f"제한 시간({settings.SITE_ANALYSIS_TIMEOUT_SECONDS}초)을 넘었습니다"
        except Exception as e:  # noqa: BLE001
            logger.exception("[site_analysis] 실행 실패 run=%s", run_id)
            run.steps, run.status, run.error = snap(steps), "failed", f"{type(e).__name__}: {e}"[:500]
        finally:
            side_events.close_channel(conv, q)
            bt.clear_handoff(run.user_id)
            run.finished_at = datetime.now(timezone.utc)
            try:
                await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("[site_analysis] 결과 저장 실패 run=%s", run_id)

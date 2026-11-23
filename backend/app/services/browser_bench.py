"""브라우저 자동화 측정 체계: 검증을 마친 사이트 시나리오를 반복 실행해 통과율·실패 원인·시간·토큰을 기록하고 집계한다.

실행은 웹사이트 분석의 재현 검증(verify)을 그대로 쓴다: 저장된 사이트 요령과 분야 샘플 입력값으로 처음부터 끝까지 수행하고(상태를 바꾸는 단계 제외),
에이전트가 보고한 단계별 결과를 평가한다. 같은 label 로 묶인 결과끼리 집계하고, label 끼리 비교하면 개선 전후를 숫자로 볼 수 있다.
실행: scripts/browser_bench.py. 개인정보 보호를 위해 메일 분야는 기본에서 제외한다 (실제 메일함을 읽는다).
"""
import asyncio
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_profile import BrowserBenchResult, SiteAnalysisRun, SiteProfile

DEFAULT_EXCLUDED_VERTICALS = ("mail",)
FLAKY_LOW, FLAKY_HIGH = 0.0, 1.0  # 통과율이 이 사이(양 끝 제외)이면 실행마다 결과가 달라지는 '불안정'

# 동작 단위 오류 분류 (브리프 문구 기준). 위에서부터 처음 맞는 것.
ERROR_RULES: list[tuple[str, str]] = [
    ("요소 번호(ref) 못 찾음", r"요소를 찾을 수 없습니다|data-agent-ref"),
    ("일괄 동작 형식 거부", r"일괄 동작을 실행하지|단계의 ref 는 앞 단계|이후 ref 가 무효"),
    ("드롭다운 항목 못 고름", r"드롭다운을 열었지만"),
    ("같은 동작 반복 차단", r"같은 동작\(.*\)을 같은 화면에서 이미|같은 화면에서 같은 동작"),
    ("승인 필요(화면 없음)", r"사용자 승인이 필요"),
    ("접속 차단·보안 확인", r"Access Denied|CAPTCHA|캡차|봇 확인|사용 안 함으로 꺼진|blocked"),
    ("시간 초과·연결", r"Timeout|시간 초과|응답이 없습니다|연결이 끊어|ERR_(NAME|CONNECTION|TIMED)|Page crashed|이동 실패"),
]
HEAL_MARK = "[자동 복구]"
INFRA_REASON = "모델 연결·실행 오류 (브라우저 동작 0건)"
MAX_CONSECUTIVE_INFRA = 3  # 이만큼 연달아 실행 환경 오류면 측정을 멈춘다


def classify_error(text: str) -> str:
    b = text or ""
    for name, rx in ERROR_RULES:
        if re.search(rx, b):
            return name
    return "기타"


def summarize_run(run: SiteAnalysisRun) -> dict:
    """재현 검증 실행 한 건 → 저장할 요약. 동작 오류를 분류하고, 통과하지 못했으면 이유를 분류한다."""
    res = run.result or {}
    errors: Counter = Counter()
    heals = 0
    for s in run.steps or []:
        if not s.get("action"):
            continue
        brief = str(s.get("brief") or "")
        if s.get("ok") is False:
            errors[classify_error(brief or str(s.get("desc") or ""))] += 1
        if brief.startswith(HEAL_MARK):
            heals += 1
    flow = [{"key": f.get("key"), "title": f.get("title"), "status": f.get("status")} for f in res.get("flow", [])]
    passed = bool(res.get("passed"))
    reasons: list[str] = []
    if not passed:
        err = str(run.error or "")
        if "제한 시간" in err:
            reasons.append("실행 제한 시간 초과")
        elif run.status != "succeeded":
            reasons.append("실행 실패: " + (err[:40] or run.status))
        elif not res or "보고하지 않았습니다" in str(res.get("summary", "")):
            reasons.append("판정 없음 (단계 제한·중단)")
        else:
            reasons += [f"단계 실패: {f['title']}" for f in flow if f["status"] in ("failed", "missing", "skipped")]
            if int(res.get("loop_blocks") or 0) > 2:
                reasons.append("같은 동작 반복")
            if not reasons:
                reasons.append("에이전트가 성공으로 보고하지 않음")
    actions = sum(1 for s in run.steps or [] if s.get("action"))
    if not passed and actions == 0 and (run.status == "succeeded" or re.search(r"Connection|연결", str(run.error or ""))):
        reasons = [INFRA_REASON]  # 브라우저를 한 번도 못 쓴 채 끝났다: 사이트가 아니라 모델 연결 같은 실행 환경 문제일 가능성이 크다 (집계에서 뺀다)
    usage = res.get("usage") or {}
    return {
        "run_status": run.status, "passed": passed, "success": bool(res.get("success")),
        "seconds": int(res.get("seconds") or 0) or None, "steps": res.get("steps"), "failed_steps": res.get("failed_steps"),
        "loop_blocks": res.get("loop_blocks"), "tokens": usage.get("total") or None, "heals": heals,
        "flow": flow, "issues": list(res.get("issues") or [])[:5], "errors": dict(errors), "reasons": reasons, "error": (run.error or None),
    }


def start_url_for(site: SiteProfile) -> str:
    """시작 주소: 진입 주소 중 자리표시자({키})가 없는 첫 번째, 없으면 첫 도메인의 홈."""
    for e in (site.spec or {}).get("entry", []):
        u = str(e.get("url") or "")
        if u and "{" not in u:
            return u
    dom = [d.strip() for d in (site.domains or "").split(",") if d.strip()]
    return f"https://{dom[0]}/" if dom else ""


def build_cases(sites: list[SiteProfile], vertical_specs: dict, sites_filter: Optional[set] = None, verticals_filter: Optional[set] = None,
                include_excluded: bool = False) -> list[dict]:
    """측정 대상: 검증됨 + 사용 중인 사이트. 분야 샘플 입력값을 쓰고, 기본에서 메일 분야는 뺀다."""
    out = []
    for s in sites:
        if s.status != "verified" or not s.enabled or not start_url_for(s):
            continue
        if sites_filter and s.name not in sites_filter:
            continue
        if verticals_filter and (s.vertical or "") not in verticals_filter:
            continue
        if not include_excluded and (s.vertical or "") in DEFAULT_EXCLUDED_VERTICALS:
            continue
        vspec = vertical_specs.get(s.vertical or "") or {}
        keys = {i["key"] for i in vspec.get("inputs", [])}
        inputs = {k: v for k, v in (vspec.get("sample") or {}).items() if k in keys and str(v).strip()}
        # 분야가 없는 사이트는 표준 플로우가 없어서 시나리오를 직접 준다
        scenario = "" if vspec.get("flow") else f"{s.name} 의 사이트 요령에 적힌 방법으로 대표적인 검색을 한 번 수행하고 결과 화면까지 확인한다 (상태를 바꾸는 동작 제외)"
        out.append({"name": s.name, "vertical": s.vertical, "start_url": start_url_for(s), "inputs": inputs, "scenario": scenario, "body": s.body or "", "spec": s.spec or {}})
    return out


def is_infra(r: dict) -> bool:
    return INFRA_REASON in (r.get("reasons") or [])


def aggregate(all_rows: list[dict]) -> dict:
    """측정 결과(dict 목록)를 사이트별·전체로 집계한다. 실행 환경 오류(모델 연결 등)로 브라우저를 못 쓴 실행은 통과율에서 빼고 따로 센다."""
    rows = [r for r in all_rows if not is_infra(r)]
    excluded = len(all_rows) - len(rows)
    by: dict = defaultdict(list)
    for r in rows:
        by[r["site_name"]].append(r)

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    sites = []
    for name, rs in sorted(by.items()):
        n = len(rs)
        rate = sum(1 for r in rs if r["passed"]) / n
        errs: Counter = Counter()
        why: Counter = Counter()
        for r in rs:
            errs.update(r.get("errors") or {})
            why.update(r.get("reasons") or [])
        sites.append({
            "site": name, "vertical": rs[0].get("vertical"), "runs": n, "pass_rate": round(rate, 2), "flaky": FLAKY_LOW < rate < FLAKY_HIGH,
            "avg_seconds": avg([r.get("seconds") for r in rs]), "avg_steps": avg([r.get("steps") for r in rs]), "avg_tokens": avg([r.get("tokens") for r in rs]),
            "heals": sum(r.get("heals") or 0 for r in rs), "errors": dict(errs.most_common()), "fail_reasons": dict(why.most_common()),
        })
    total = len(rows)
    all_err: Counter = Counter()
    all_why: Counter = Counter()
    for r in rows:
        all_err.update(r.get("errors") or {})
        all_why.update(r.get("reasons") or [])
    actions = sum(r.get("steps") or 0 for r in rows)
    return {
        "excluded_infra": excluded,
        "runs": total, "passed": sum(1 for r in rows if r["passed"]), "pass_rate": round(sum(1 for r in rows if r["passed"]) / total, 2) if total else None,
        "flaky_sites": [s["site"] for s in sites if s["flaky"]], "avg_seconds": avg([r.get("seconds") for r in rows]), "avg_steps": avg([r.get("steps") for r in rows]),
        "avg_tokens": avg([r.get("tokens") for r in rows]), "heals": sum(r.get("heals") or 0 for r in rows),
        "action_error_rate": round(sum(all_err.values()) / actions, 3) if actions else None,
        "errors": dict(all_err.most_common()), "fail_reasons": dict(all_why.most_common()), "sites": sites,
    }


def compare(a: dict, b: dict) -> list[dict]:
    """두 집계(a=기준, b=이후)의 사이트별 통과율·시간 변화. 한쪽에만 있는 사이트는 None."""
    sa_, sb_ = {s["site"]: s for s in a["sites"]}, {s["site"]: s for s in b["sites"]}
    rows = []
    for name in sorted(set(sa_) | set(sb_)):
        x, y = sa_.get(name), sb_.get(name)
        rows.append({"site": name, "pass_a": x and x["pass_rate"], "pass_b": y and y["pass_rate"],
                     "delta": (y["pass_rate"] - x["pass_rate"]) if x and y else None,
                     "sec_a": x and x["avg_seconds"], "sec_b": y and y["avg_seconds"]})
    return rows


def to_dict(r: BrowserBenchResult) -> dict:
    return {c: getattr(r, c) for c in ("label", "site_name", "vertical", "attempt", "run_id", "run_status", "passed", "success", "seconds", "steps", "failed_steps",
                                         "loop_blocks", "tokens", "heals", "flow", "issues", "errors", "reasons", "env", "error")} | {"created_at": r.created_at}


async def load_results(db: AsyncSession, label: str) -> list[dict]:
    rows = (await db.execute(select(BrowserBenchResult).where(BrowserBenchResult.label == label).order_by(BrowserBenchResult.created_at))).scalars().all()
    return [to_dict(r) for r in rows]


async def list_labels(db: AsyncSession) -> list[dict]:
    rows = (await db.execute(select(BrowserBenchResult.label, BrowserBenchResult.passed, BrowserBenchResult.created_at))).all()
    agg: dict = {}
    for label, passed, at in rows:
        a = agg.setdefault(label, {"label": label, "runs": 0, "passed": 0, "last": at})
        a["runs"] += 1
        a["passed"] += 1 if passed else 0
        a["last"] = max(a["last"], at) if a["last"] and at else (a["last"] or at)
    return sorted(({**v, "pass_rate": round(v["passed"] / v["runs"], 2)} for v in agg.values()), key=lambda x: x["last"] or datetime.min, reverse=True)


async def llm_reachable(timeout: int = 40) -> tuple[bool, str]:
    """측정을 시작하기 전에 모델에 연결되는지 확인한다 (연결이 안 되면 모든 실행이 1초 만에 실패해 시간만 쓴다)."""
    from app.agent.react_agent import AgentRunner

    try:
        await asyncio.wait_for(AgentRunner(tools=[]).llm.ainvoke("한 단어로만 답하세요: 안녕"), timeout)
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:120]}"


async def run_batch(user_id: str, cases: list[dict], label: str, attempts: int = 3, progress: Optional[Callable[[str], None]] = None) -> int:
    """cases 를 attempts 회 반복 실행한다. 시간대·사이트 상태의 영향을 고르게 받도록 '모든 사이트 1회 → 2회 …' 순으로 돈다. 저장한 결과 수를 돌려준다.
    시작 전에 모델 연결을 확인하고, 실행 환경 오류가 연달아 나면 멈춘다. 한 실행이 제한 시간을 한참 넘기면 중단한다."""
    from app.config import settings
    from app.db.session import AsyncSessionLocal
    from app.services import site_analysis_service as sa
    from app.services import site_profile_service as svc
    from app.tools.browser_tools import DAEMON_VERSION

    say = progress or (lambda _m: None)
    ok, why = await llm_reachable()
    if not ok:
        raise RuntimeError(f"모델에 연결할 수 없어 측정을 시작하지 않았습니다 ({why}). 네트워크·사내 게이트웨이(VPN 등)를 확인하세요")
    saved, infra_streak = 0, 0
    for attempt in range(1, attempts + 1):
        for i, c in enumerate(cases, 1):
            async with AsyncSessionLocal() as db:
                await svc.refresh(db)  # 서버와 같은 사이트 요령으로
                try:
                    run = await sa.start(db, user_id, {"mode": "verify", "name": c["name"], "vertical": c["vertical"], "start_url": c["start_url"], "scenario": c.get("scenario", ""),
                                                       "draft_body": c["body"], "draft_spec": c["spec"], "inputs": c["inputs"]})
                except sa.AnalysisError as e:
                    say(f"[{attempt}/{attempts}] {c['name']}: 시작하지 못함 ({e.detail})")
                    continue
                rid = run.id
            hung = False
            try:  # 제한 시간(+여유)을 넘겨 멈춰 있으면 중단한다 (모델 연결이 끊긴 채 매달리는 경우)
                await asyncio.wait_for(asyncio.shield(sa._tasks[rid]), settings.SITE_ANALYSIS_TIMEOUT_SECONDS + 180)
            except asyncio.TimeoutError:
                hung = True
                sa._tasks[rid].cancel()
                try:
                    await sa._tasks[rid]
                except BaseException:  # noqa: BLE001
                    pass
            async with AsyncSessionLocal() as db:
                run = await sa.get_run(db, user_id, rid)
                s = summarize_run(run)
                if hung:
                    s["reasons"] = ["실행 제한 시간 초과 (멈춤)"] + [r for r in s["reasons"] if r != INFRA_REASON]
                db.add(BrowserBenchResult(label=label, site_name=c["name"], vertical=c["vertical"], attempt=attempt, run_id=rid, env={"daemon": DAEMON_VERSION, "llm": settings.LLM_TYPE}, **s))
                await db.commit()
            saved += 1
            infra_streak = infra_streak + 1 if INFRA_REASON in s["reasons"] else 0
            say(f"[{attempt}/{attempts}] ({i}/{len(cases)}) {c['name']}: {'통과' if s['passed'] else '실패'} · {s['seconds']}초 · {s['steps']}동작" + ("" if s["passed"] else " · " + ", ".join(s["reasons"][:2])))
            if infra_streak >= MAX_CONSECUTIVE_INFRA:
                raise RuntimeError(f"실행 환경 오류(브라우저 동작 0건)가 {infra_streak}번 연달아 나서 측정을 멈췄습니다. 모델 연결을 확인하고 다시 실행하세요 (저장된 {saved}건은 집계에서 제외됩니다)")
    return saved

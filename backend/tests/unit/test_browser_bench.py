"""브라우저 자동화 측정: 오류 분류, 실행 요약, 대상 선정, 집계·비교 (순수 함수)."""
from types import SimpleNamespace

from app.services import browser_bench as bb


def run(steps=(), result=None, status="succeeded", error=None):
    return SimpleNamespace(steps=list(steps), result=result, status=status, error=error)


def st(ok, brief, action="click"):
    return {"action": action, "ok": ok, "brief": brief, "desc": brief}


def test_classify_error_groups_known_messages():
    assert bb.classify_error("Error: ref 47 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요") == "요소 번호(ref) 못 찾음"
    assert bb.classify_error("Error: 일괄 동작을 실행하지 않았습니다 — 3번째 단계가 …") == "일괄 동작 형식 거부"
    assert bb.classify_error("Error: 드롭다운을 열었지만 “낮은 요금 순” 항목을 고르지 못했습니다") == "드롭다운 항목 못 고름"
    assert bb.classify_error("Error: 같은 동작(scroll)을 같은 화면에서 이미 4번 했는데") == "같은 동작 반복 차단"
    assert bb.classify_error("Title: Access Denied") == "접속 차단·보안 확인"
    assert bb.classify_error("Error: 이동 실패: net::ERR_NAME_NOT_RESOLVED") == "시간 초과·연결"
    assert bb.classify_error("뭔가 다른 오류") == "기타"


def test_summarize_run_counts_errors_heals_and_failure_reasons():
    flow = [{"key": "search", "title": "검색", "status": "reached"}, {"key": "room", "title": "객실 요금", "status": "failed"}]
    r = run([st(True, "[자동 복구] 요소 번호가 바뀌어 …"), st(False, "Error: ref 3 요소를 찾을 수 없습니다"), st(False, "Error: ref 4 요소를 찾을 수 없습니다"), st(True, "화면 읽기", "snapshot"), {"ok": None}],
            {"passed": False, "success": False, "seconds": 61, "steps": 4, "failed_steps": 2, "loop_blocks": 0, "flow": flow, "issues": ["a"], "usage": {"total": 1234}})
    s = bb.summarize_run(r)
    assert s["errors"] == {"요소 번호(ref) 못 찾음": 2} and s["heals"] == 1 and s["tokens"] == 1234 and s["seconds"] == 61
    assert s["reasons"] == ["단계 실패: 객실 요금"] and s["passed"] is False


def test_summarize_run_failure_reasons_for_timeout_and_no_verdict_and_pass():
    assert bb.summarize_run(run([], None, "failed", "제한 시간(600초)을 넘었습니다"))["reasons"] == ["실행 제한 시간 초과"]
    assert bb.summarize_run(run([st(True, "x")], {"passed": False, "summary": "에이전트가 검증 결과를 보고하지 않았습니다 (…)", "flow": []}))["reasons"] == ["판정 없음 (단계 제한·중단)"]  # 동작은 했는데 판정이 없다
    ok = bb.summarize_run(run([st(True, "x")], {"passed": True, "success": True, "seconds": 30, "steps": 1, "flow": []}))
    assert ok["passed"] is True and ok["reasons"] == [] and ok["tokens"] is None


def site(name, vertical="shopping", status="verified", enabled=True, domains="a.com", spec=None):
    return SimpleNamespace(name=name, vertical=vertical, status=status, enabled=enabled, domains=domains, spec=spec or {}, body="본문")


def test_build_cases_skips_drafts_disabled_and_mail_and_uses_vertical_samples():
    vs = {"shopping": {"inputs": [{"key": "query"}], "sample": {"query": "라면", "sort": "x"}, "flow": [{"key": "search"}]}}
    sites = [site("다나와"), site("초안", status="draft"), site("꺼짐", enabled=False), site("메일", vertical="mail"), site("검색엔진", vertical=None, domains="google.com"),
             site("진입주소", spec={"entry": [{"url": "https://x.com/{q}"}, {"url": "https://x.com/home"}]})]
    cases = bb.build_cases(sites, vs)
    assert [c["name"] for c in cases] == ["다나와", "검색엔진", "진입주소"]
    assert cases[0]["inputs"] == {"query": "라면"} and cases[0]["scenario"] == ""  # 분야에 정의된 입력값만
    assert "대표적인 검색" in cases[1]["scenario"]  # 분야가 없으면 시나리오를 준다
    assert cases[2]["start_url"] == "https://x.com/home"  # 자리표시자가 없는 진입 주소
    assert [c["name"] for c in bb.build_cases(sites, vs, include_excluded=True)][-1] == "진입주소" and len(bb.build_cases(sites, vs, include_excluded=True)) == 4
    assert [c["name"] for c in bb.build_cases(sites, vs, sites_filter={"다나와"})] == ["다나와"]


def row(site_name, passed, seconds=60, steps=10, errors=None, reasons=None, tokens=None, heals=0):
    return {"site_name": site_name, "vertical": "x", "passed": passed, "seconds": seconds, "steps": steps, "errors": errors or {}, "reasons": reasons or [], "tokens": tokens, "heals": heals}


def test_aggregate_computes_rates_flaky_and_error_rate():
    rows = [row("A", True), row("A", False, errors={"요소 번호(ref) 못 찾음": 2}, reasons=["단계 실패: 검색"]), row("A", True), row("B", False, reasons=["판정 없음 (단계 제한·중단)"]), row("B", False)]
    g = bb.aggregate(rows)
    assert g["runs"] == 5 and g["passed"] == 2 and g["pass_rate"] == 0.4 and g["flaky_sites"] == ["A"]
    a = next(s for s in g["sites"] if s["site"] == "A")
    assert a["pass_rate"] == 0.67 and a["flaky"] and a["errors"] == {"요소 번호(ref) 못 찾음": 2}
    assert g["action_error_rate"] == round(2 / 50, 3) and g["fail_reasons"]["단계 실패: 검색"] == 1
    assert bb.aggregate([])["pass_rate"] is None


def test_compare_shows_delta_and_missing_sites():
    a = bb.aggregate([row("A", False), row("A", False), row("B", True)])
    b = bb.aggregate([row("A", True), row("A", False), row("C", True)])
    rows = {r["site"]: r for r in bb.compare(a, b)}
    assert rows["A"]["pass_a"] == 0 and rows["A"]["pass_b"] == 0.5 and rows["A"]["delta"] == 0.5
    assert rows["B"]["pass_b"] is None and rows["B"]["delta"] is None and rows["C"]["pass_a"] is None


def test_zero_action_failure_is_infra_and_excluded_from_aggregate():
    """브라우저를 한 번도 못 쓰고 끝난 실패는 모델 연결 같은 환경 문제로 보고 통과율에서 뺀다."""
    infra = bb.summarize_run(run([], {"passed": False, "summary": "에이전트가 검증 결과를 보고하지 않았습니다 (…)", "flow": [], "seconds": 1}))
    assert infra["reasons"] == [bb.INFRA_REASON]
    ok = bb.summarize_run(run([st(True, "x")], {"passed": True, "success": True, "seconds": 30, "steps": 1, "flow": []}))
    real_fail = bb.summarize_run(run([st(True, "x")], {"passed": False, "summary": "…", "flow": [{"key": "a", "title": "검색", "status": "failed"}], "steps": 1}))
    rows = [{"site_name": "A", **infra}, {"site_name": "A", **infra}, {"site_name": "A", **ok}, {"site_name": "A", **real_fail}]
    g = bb.aggregate(rows)
    assert g["excluded_infra"] == 2 and g["runs"] == 2 and g["pass_rate"] == 0.5  # 환경 오류 2회는 빠진다
    assert bb.aggregate([{"site_name": "A", **infra}])["pass_rate"] is None


def test_site_specific_sample_inputs_replace_values_the_site_does_not_have():
    """롯데시네마에는 '강남' 극장이 없어서 분야 샘플 그대로면 항상 실패로 집계된다 → 사이트별 입력값으로 바꾼다."""
    from types import SimpleNamespace
    from app.services import browser_bench as bb

    site = SimpleNamespace(name="롯데시네마", status="verified", enabled=True, vertical="movie", domains="lottecinema.co.kr", aliases="", body="", spec={})
    vspec = {"movie": {"inputs": [{"key": "theater"}, {"key": "date"}], "sample": {"theater": "강남", "date": "내일"}, "flow": [{"key": "x"}]}}
    case = bb.build_cases([site], vspec)[0]
    assert case["inputs"] == {"theater": "월드타워", "date": "내일"}

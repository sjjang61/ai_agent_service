"""브라우저 에이전트 효율화: 스냅샷 압축 형식, 변화 없음 감지, batch 동작."""
import asyncio
import json

import pytest

from app.tools import browser_tools as bt

PAGE = "https://shop.example.com/search?q=a"


def _els(n=120):
    return [{"ref": i, "tag": "a", "label": f"상품 {i}", "href": f"https://shop.example.com/item/{i}"} for i in range(1, n + 1)]


def test_compact_format_is_much_smaller_than_json_lines():
    els = _els()
    old = "\n".join(json.dumps(e, ensure_ascii=False) for e in els)
    new = "\n".join(bt.compact_elements(els, PAGE))
    assert len(new) < len(old) * 0.6  # 40% 이상 감소
    assert '[3] a "상품 3" href=/item/3' in new  # 같은 사이트 링크는 경로만


def test_compact_elements_dedups_and_keeps_inputs():
    els = [
        {"ref": 1, "tag": "a", "label": "홈", "href": "https://shop.example.com/"},
        {"ref": 2, "tag": "a", "label": "홈", "href": "https://shop.example.com/"},  # 중복
        {"ref": 3, "tag": "input", "type": "text", "name": "q", "placeholder": "검색", "value": "노트북"},
        {"ref": 4, "tag": "input", "type": "text", "name": "q", "placeholder": "검색", "value": "노트북"},  # 입력창은 중복이어도 유지
        {"ref": 5, "tag": "input", "type": "checkbox", "checked": True, "label": "재고만"},
        {"ref": 6, "tag": "button", "label": "검색", "disabled": True},
    ]
    lines = bt.compact_elements(els, PAGE)
    assert [ln.split("]")[0] for ln in lines] == ["[1", "[3", "[4", "[5", "[6"]
    assert 'placeholder="검색"' in lines[1] and 'value="노트북"' in lines[1]
    assert "checked" in lines[3] and "disabled" in lines[4]


def test_external_href_kept_absolute():
    line = bt.compact_elements([{"ref": 1, "tag": "a", "label": "외부", "href": "https://other.com/x"}], PAGE)[0]
    assert "href=https://other.com/x" in line


def test_format_full_keeps_untrusted_fence_and_shrinks_text():
    res = {"ok": True, "url": PAGE, "title": "T", "elements": _els(), "text": "줄1\n\n\n\n줄2   끝"}
    out = bt._format(res)
    assert "<<<WEB_CONTENT>>>" in out and "UNTRUSTED" in out
    assert "줄1\n줄2 끝" in out  # 빈 줄·중복 공백 정리


def test_old_snapshot_compaction_still_works_on_new_format():
    big = bt._format({"ok": True, "url": PAGE, "title": "T", "elements": _els(), "text": "본문 " * 800})
    small = bt.compact_snapshot(big)
    assert len(small) < 1200 and "URL:" in small and "[5]" not in small and "본문" in small


# ---- batch 검증 ----
def S(action, **kw):
    return bt.BatchStep(action=action, **kw)


def test_validate_batch_rules():
    assert bt.validate_batch(None) and bt.validate_batch([])
    ok = [S("type", ref=1, text="a"), S("select", ref=2, text="b"), S("click", ref=3)]
    assert bt.validate_batch(ok) is None
    assert "ref 가 무효" in bt.validate_batch([S("click", ref=1), S("type", ref=2, text="x")])  # 중간 click
    assert bt.validate_batch([S("type", ref=1, text="a", submit=True), S("type", ref=2, text="b")])  # 중간 submit
    assert "ref 또는 label" in bt.validate_batch([S("type", text="a")])
    assert "최대" in bt.validate_batch([S("type", ref=1, text="a")] * (bt.MAX_BATCH_STEPS + 1))
    assert bt.validate_batch([S("type", ref=1, text="a", submit=True)]) is None  # 마지막은 submit 가능


# ---- 도구 동작 (browser_call 을 가짜로) ----
class Fake:
    def __init__(self, page=None):
        self.calls = []
        self.page = page or {"ok": True, "url": PAGE, "title": "T", "elements": _els(5), "text": "본문"}

    async def __call__(self, user_id, payload, **kw):
        self.calls.append(payload)
        cmd = payload["cmd"]
        if payload.get("ref") == 99:
            return {"ok": False, "error": "TimeoutError: element not found"}
        if cmd in ("type", "select"):
            return {"ok": True, "url": PAGE}
        return dict(self.page)


@pytest.fixture
def tool(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    t._fake = fake
    return t


@pytest.mark.asyncio
async def test_batch_runs_all_steps_in_one_call_and_returns_snapshot(tool):
    out = await tool._arun("batch", steps=[
        {"action": "type", "ref": 1, "text": "서울"},
        {"action": "select", "ref": 2, "text": "2명"},
        {"action": "click", "ref": 3},
    ])
    assert [c["cmd"] for c in tool._fake.calls] == ["type", "select", "click"]
    assert "1. type ref=1 → 완료" in out and "3. click ref=3 → 완료" in out
    assert "Interactive elements" in out  # 마지막 click 의 새 화면


@pytest.mark.asyncio
async def test_batch_ending_with_type_appends_snapshot(tool):
    out = await tool._arun("batch", steps=[{"action": "type", "ref": 1, "text": "a"}, {"action": "type", "ref": 2, "text": "b"}])
    assert [c["cmd"] for c in tool._fake.calls] == ["type", "type", "snapshot"]
    assert "Interactive elements" in out


@pytest.mark.asyncio
async def test_batch_stops_at_first_error(tool):
    out = await tool._arun("batch", steps=[
        {"action": "type", "ref": 1, "text": "a"},
        {"action": "type", "ref": 99, "text": "b"},
        {"action": "type", "ref": 3, "text": "c"},
    ])
    assert [c["ref"] for c in tool._fake.calls if "ref" in c] == [1, 99]  # 3번은 실행 안 함
    assert "2. type ref=99 → 실패" in out and "1단계는 실행하지 않았습니다" in out


@pytest.mark.asyncio
async def test_batch_invalid_is_rejected_without_running(tool):
    out = await tool._arun("batch", steps=[{"action": "click", "ref": 1}, {"action": "type", "ref": 2, "text": "x"}])
    assert out.startswith("Error") and tool._fake.calls == []


@pytest.mark.asyncio
async def test_batch_each_step_goes_through_approval(tool, monkeypatch):
    asked = []

    async def deny(self, payload):
        asked.append(payload["cmd"])
        return "[사용자가 이 동작을 거부했습니다. 멈추세요.]" if payload["cmd"] == "click" else None

    async def yes(self):
        return True

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", yes)
    monkeypatch.setattr(bt.BrowserActionTool, "_approve", deny)
    out = await tool._arun("batch", steps=[{"action": "type", "ref": 1, "text": "a"}, {"action": "click", "ref": 2}])
    assert asked == ["type", "click"]  # 단계마다 정책 검사
    assert [c["cmd"] for c in tool._fake.calls] == ["type"]  # 거부된 click 은 브라우저로 가지 않는다
    assert "2. click ref=2 → 실패" in out and "거부" in out


@pytest.mark.asyncio
async def test_batch_blocked_by_domain_policy_applies_only_to_goto_so_batch_has_no_goto():
    assert "goto" not in bt.BatchStep.model_fields["action"].annotation.__args__


@pytest.mark.asyncio
async def test_unchanged_screen_is_reported_briefly(tool):
    first = await tool._arun("click", ref=1)
    assert "Interactive elements" in first  # 첫 결과는 전체
    second = await tool._arun("click", ref=1)
    assert "화면 변화 없음" in second and "Interactive elements" not in second and len(second) < 300
    snap = await tool._arun("snapshot")  # 명시적 snapshot 은 항상 전체
    assert "Interactive elements" in snap
    tool._fake.page = {**tool._fake.page, "text": "본문 바뀜"}
    third = await tool._arun("click", ref=1)
    assert "Interactive elements" in third  # 바뀌면 다시 전체


# ---- label 지정 ----
ELS = [
    {"ref": 1, "tag": "button", "label": "가는날"},
    {"ref": 2, "tag": "button", "label": "27"},
    {"ref": 3, "tag": "button", "label": "27일 출발", "disabled": True},
    {"ref": 4, "tag": "button", "label": "적용"},
    {"ref": 5, "tag": "button", "label": "성인 +"},
    {"ref": 6, "tag": "button", "label": "소아 +"},
    {"ref": 7, "tag": "button", "label": "더보기"},
    {"ref": 8, "tag": "button", "label": "더보기"},
    {"ref": 9, "tag": "input", "placeholder": "도착지", "name": "arr"},
]


def test_resolve_label():
    assert bt.resolve_label(ELS, "가는날") == (1, "")
    assert bt.resolve_label(ELS, "  가는날 ") == (1, "")  # 앞뒤 공백 정규화
    assert bt.resolve_label(ELS, "27") == (2, "")  # 정확 일치 우선 (부분 일치 3번은 비활성)
    assert bt.resolve_label(ELS, "성인")[0] == 5  # 부분 일치가 하나면 선택
    assert bt.resolve_label(ELS, "도착지")[0] == 9  # placeholder
    ref, why = bt.resolve_label(ELS, "더보기")
    assert ref is None and "2개" in why and "[7]" in why and "[8]" in why
    assert bt.resolve_label(ELS, "더보기", nth=2) == (8, "")
    assert bt.resolve_label(ELS, "더보기", nth=3)[0] is None
    assert "찾지 못했습니다" in bt.resolve_label(ELS, "없는버튼")[1]


def test_validate_label_batch_rules():
    ok = [S("click", label="가는날"), S("click", label="27"), S("click", label="적용")]
    assert bt.validate_batch(ok) is None  # label 클릭은 중간에도 가능
    ref_after_label = [S("click", label="가는날"), S("type", ref=3, text="x")]
    assert "label 을 쓰세요" in bt.validate_batch(ref_after_label)
    assert bt.validate_batch([S("type", ref=1, text="a"), S("click", label="검색")]) is None  # ref 입력 뒤 label 클릭은 OK
    assert bt.validate_batch([S("press", key="Escape"), S("click", ref=2)])  # press 뒤 ref 는 무효


class Widget:
    """snapshot 마다 화면이 달라지는 가짜 위젯: 클릭할 때마다 단계가 진행된다."""

    def __init__(self):
        self.calls = []
        self.stage = 0

    def page(self):
        screens = [
            [{"ref": 1, "tag": "button", "label": "가는날"}],
            [{"ref": 1, "tag": "button", "label": "26"}, {"ref": 2, "tag": "button", "label": "27"}],
            [{"ref": 1, "tag": "button", "label": "적용"}],
            [{"ref": 1, "tag": "button", "label": "완료됨"}],
        ]
        return {"ok": True, "url": PAGE, "title": "T", "elements": screens[min(self.stage, 3)], "text": f"단계 {self.stage}"}

    async def __call__(self, user_id, payload, **kw):
        self.calls.append((payload["cmd"], payload.get("ref")))
        if payload["cmd"] == "click":
            self.stage += 1
        return self.page()


@pytest.fixture
def widget_tool(monkeypatch):
    w = Widget()
    monkeypatch.setattr(bt, "browser_call", w)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    t._w = w
    return t


@pytest.mark.asyncio
async def test_label_batch_walks_a_widget_in_one_call(widget_tool):
    out = await widget_tool._arun("batch", steps=[
        {"action": "click", "label": "가는날"}, {"action": "click", "label": "27"}, {"action": "click", "label": "적용"}])
    clicks = [c for c in widget_tool._w.calls if c[0] == "click"]
    assert clicks == [("click", 1), ("click", 2), ("click", 1)]  # 단계마다 화면이 바뀌어 같은 ref 번호가 다른 요소지만 label 로 정확히 찾았다
    assert "1. click label='가는날' → ref 1 → 완료" in out and "2. click label='27' → ref 2 → 완료" in out
    assert "완료됨" in out  # 마지막 화면


@pytest.mark.asyncio
async def test_label_batch_stops_when_label_missing_or_ambiguous(widget_tool):
    out = await widget_tool._arun("batch", steps=[
        {"action": "click", "label": "가는날"}, {"action": "click", "label": "28"}, {"action": "click", "label": "적용"}])
    assert sum(1 for c in widget_tool._w.calls if c[0] == "click") == 1  # 두 번째에서 멈춤
    assert "2. click label='28' → 실패" in out and "찾지 못했습니다" in out and "1단계는 실행하지 않았습니다" in out


@pytest.mark.asyncio
async def test_label_click_goes_through_approval_with_resolved_element(widget_tool, monkeypatch):
    seen = []

    async def spy(self, payload):
        seen.append((payload["cmd"], payload.get("ref"), [e["label"] for e in self.last_elements]))
        return None

    async def yes(self):
        return True

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", yes)
    monkeypatch.setattr(bt.BrowserActionTool, "_approve", spy)
    await widget_tool._arun("batch", steps=[{"action": "click", "label": "가는날"}, {"action": "click", "label": "27"}])
    clicks = [x for x in seen if x[0] == "click"]
    assert clicks[1][1] == 2 and "27" in clicks[1][2]  # 승인 판정은 새로 읽은 화면의 요소 기준


# ---- 스크린샷 ----
def test_daemon_shoots_on_screen_changes_and_events():
    src = bt.DAEMON_SOURCE
    assert 'cmd == "shot"' in src
    sel = src[src.index('if cmd == "select"'):src.index('if cmd == "press"')]
    assert "shot(" in sel  # select 도 남긴다
    scr = src[src.index('if cmd == "scroll"'):src.index('if cmd == "wait"')]
    assert "shot(" in scr  # scroll 도 남긴다
    assert bt.DAEMON_VERSION == 29 and "VERSION = 9333, 900, 29" in src


class _LocalFake:
    def __init__(self, same_image=False, same_screen=False):
        self.calls = []
        self.same = same_image
        self.same_screen = same_screen  # True 면 모든 동작이 같은 화면(같은 내용)을 돌려준다
        self.n = 0
        self.k = 0

    async def __call__(self, user_id, payload, **kw):
        self.calls.append(payload["cmd"])
        if payload["cmd"] == "frame":
            self.n += 1
            return {"ok": True, "img": "eA==" if self.same else f"img{self.n}", "url": PAGE, "title": "T"}
        self.k += 1
        text = "\n".join(f"고정 줄 {i}" for i in range(20)) if self.same_screen else "\n".join(f"화면{self.k} 줄 {i}" for i in range(20))
        return {"ok": True, "url": PAGE, "title": "T", "elements": _els(3), "text": text, "sy": 0}


@pytest.mark.asyncio
async def test_local_browser_records_shot_after_screen_changing_actions(monkeypatch):
    fake, saved = _LocalFake(), []
    monkeypatch.setattr(bt, "browser_call", fake)

    async def save(user_id, cid, img, url, title, run):
        saved.append((url, title, run))
        return True

    monkeypatch.setattr(bt, "save_local_shot", save)
    import app.services.local_browser as lb
    monkeypatch.setattr(lb, "route_for", lambda *a, **k: _coro(object()))

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1", run_tag="r1")
    for action, kw in (("goto", {"url": "https://x.com"}), ("click", {"ref": 1}), ("press", {"key": "Enter"}), ("scroll", {"direction": "down"}),
                       ("select", {"ref": 1, "text": "a"}), ("back", {}), ("type", {"ref": 1, "text": "q", "submit": True})):
        saved.clear()
        await t._arun(action, **kw)
        assert saved == [(PAGE, "T", "r1")], action
    saved.clear()
    await t._arun("snapshot")
    await t._arun("type", ref=1, text="q")  # submit 없는 입력은 화면 변화로 보지 않는다
    assert saved == []


async def _coro(v):
    return v


@pytest.mark.asyncio
async def test_sandbox_browser_does_not_double_shoot_actions_but_shoots_on_failure(monkeypatch):
    fake = Fake()
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1", run_tag="r2")
    await t._arun("click", ref=1)
    assert [c["cmd"] for c in fake.calls] == ["click"]  # 데몬이 스스로 남기므로 추가 호출 없음
    await t._arun("click", ref=99)  # 실패
    assert [c["cmd"] for c in fake.calls][-1] == "shot" and fake.calls[-1]["run"] == "r2"


@pytest.mark.asyncio
async def test_event_shots_on_captcha_and_approval(monkeypatch):
    fake = Fake({"ok": True, "url": "https://x.com/captcha", "title": "T", "elements": _els(2), "text": "Press and hold to verify you are human"})
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    async def solved(self, res):
        return res, ""

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    monkeypatch.setattr(bt.BrowserActionTool, "_let_user_solve", solved)
    t = bt.BrowserActionTool(user_id="u1", conversation_id="c", login_enabled=True, run_tag="r3")
    await t._arun("goto", url="https://x.com/captcha")
    assert [c["cmd"] for c in fake.calls] == ["goto", "shot"]  # CAPTCHA 화면을 남긴다


# ---- todo 상태 알림 (계획 단계 귀속) ----
@pytest.mark.asyncio
async def test_todo_emits_plan_hint_immediately_for_state_changes():
    from app.agent import side_events
    from app.tools.interaction_tools import TodoTool, _todo_store, seed_todos

    cid = "conv-hint"
    q = side_events.open_channel(cid)
    try:
        seed_todos(cid, ["조회한다", "정리한다"])
        tool = TodoTool(conversation_id=cid)
        await tool._arun(action="read")
        assert q.empty()  # 읽기는 알리지 않는다
        out = await tool._arun(action="start", id="2")
        ev = q.get_nowait()
        assert ev["type"] == "tool_result" and ev["tool"] == "todo" and ev["call_id"].startswith("plan_hint_")
        assert ev["output"] == out and json.loads(ev["output"])["todos"][1]["status"] == "in_progress"
        bad = await tool._arun(action="start", id="99")  # 실패는 알리지 않는다
        assert bad.startswith("Error") and q.empty()
    finally:
        side_events.close_channel(cid, q)
        _todo_store.pop(cid, None)


# ---- 작업별 소요 시간 ----
def test_side_events_are_stamped_with_time():
    import time as _t

    from app.agent import side_events

    q = side_events.open_channel("conv-ts")
    try:
        before = int(_t.time() * 1000)
        side_events.emit("conv-ts", {"type": "tool_call", "tool": "browser_action"})
        side_events.emit("conv-ts", {"type": "tool_result", "tool": "browser_action", "ts": 123})  # 이미 있으면 덮어쓰지 않는다
        a, b = q.get_nowait(), q.get_nowait()
        assert before <= a["ts"] <= int(_t.time() * 1000) and b["ts"] == 123
    finally:
        side_events.close_channel("conv-ts", q)


def test_tool_events_carry_ts_and_agno_measured_duration():
    from types import SimpleNamespace as NS

    from app.agent.agno_engine import _tool_call_event, _tool_result_event

    tool = NS(tool_name="cli_browser_agent", tool_args={}, tool_call_id="c1", result="ok", tool_call_error=False, metrics=NS(duration=12.34))
    call, res = _tool_call_event(tool), _tool_result_event(tool)
    assert isinstance(call["ts"], int) and isinstance(res["ts"], int)
    assert res["duration_ms"] == 12340 and "duration_ms" not in call
    nometrics = NS(tool_name="x", tool_args={}, tool_call_id="c2", result="ok", tool_call_error=False, metrics=None)
    assert "duration_ms" not in _tool_result_event(nometrics)


# ---- 반복 차단 / 변화 요약 / 로컬 포커스 ----
class Toggle:
    """요소 30 을 누를 때마다 패널이 열렸다 닫히는 페이지 (A↔B)."""

    def __init__(self):
        self.calls = []
        self.open = False

    def screen(self):
        els = [{"ref": 1, "tag": "a", "label": "홈", "href": "https://x.com/"}, {"ref": 30, "tag": "button", "label": "출발 시간"}]
        if self.open:
            els += [{"ref": 31, "tag": "button", "label": "오전"}, {"ref": 32, "tag": "button", "label": "오후"}]
        return {"ok": True, "url": "https://x.com/list", "title": "T", "elements": els, "text": "패널 열림" if self.open else "목록"}

    async def __call__(self, user_id, payload, **kw):
        self.calls.append(payload["cmd"])
        if payload["cmd"] == "click" and payload.get("ref") == 30:
            self.open = not self.open
        return self.screen()


@pytest.fixture
def toggle_tool(monkeypatch):
    fake = Toggle()
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    t._fake = fake
    return t


@pytest.mark.asyncio
async def test_repeating_same_action_on_same_screen_is_warned_then_blocked(toggle_tool):
    t, fake = toggle_tool, toggle_tool._fake
    await t._arun("goto", url="https://x.com/list")
    r1 = await t._arun("click", ref=30)  # 열림 (A→B)
    r2 = await t._arun("click", ref=30)  # 닫힘 (B→A)
    r3 = await t._arun("click", ref=30)  # A 에서 두 번째: 경고
    assert "경고" not in r1 and "경고" not in r2 and "경고" in r3
    sent = fake.calls.count("click")
    r4 = await t._arun("click", ref=30)  # B 에서 두 번째
    r5 = await t._arun("click", ref=30)  # A 에서 세 번째 → 차단
    assert r5.startswith("Error") and "실행하지 않았습니다" in r5 and "goto" in r5
    assert fake.calls.count("click") == sent + 1  # r4 만 실행됐고 r5 는 브라우저로 가지 않았다
    r6 = await t._arun("click", ref=30)
    r7 = await t._arun("click", ref=30)
    assert "최종 보고" in r7  # 세 번째 차단부터는 그만두고 보고하라고 한다


@pytest.mark.asyncio
async def test_other_actions_are_not_blocked_by_a_loop(toggle_tool):
    t = toggle_tool
    await t._arun("goto", url="https://x.com/list")
    for _ in range(5):
        await t._arun("click", ref=30)
    assert (await t._arun("click", ref=1)).startswith("Error") is False  # 다른 요소는 가능
    assert (await t._arun("snapshot")).startswith("URL:")  # 읽기 동작은 막지 않는다
    assert (await t._arun("goto", url="https://x.com/other")).startswith("URL:")


@pytest.mark.asyncio
async def test_change_summary_reports_what_a_click_changed(toggle_tool):
    t = toggle_tool
    first = await t._arun("goto", url="https://x.com/list")
    assert "화면 변화" not in first  # goto 는 요약하지 않는다
    opened = await t._arun("click", ref=30)
    assert "[화면 변화: 요소 +2 −0 · 본문 변경]" in opened
    assert "오전" in opened and "오후" in opened and "UNTRUSTED" in opened  # 새로 나타난 요소 (웹 내용이라 구역 안에)
    closed = await t._arun("click", ref=30)
    assert "[화면 변화: 요소 +0 −2 · 본문 변경]" in closed


# ---- 로컬 브라우저: 포커스 에뮬레이션 ----
@pytest.mark.asyncio
async def test_local_browser_enables_focus_emulation_on_connect(monkeypatch):
    import app.services.local_browser as lb

    sent = []

    class _Ws:
        close_code = None

        async def send(self, data):
            sent.append(json.loads(data))
            self._last = json.loads(data)["id"]

        async def recv(self):
            return json.dumps({"id": self._last, "result": {}})

    async def connect(*a, **k):
        return _Ws()

    async def find(self):
        return "ws://x"

    monkeypatch.setattr(lb.websockets, "connect", connect)
    monkeypatch.setattr(lb.LocalBrowser, "_find_ws_url", find)
    b = lb.LocalBrowser("http://127.0.0.1:9222")
    await b._connect()
    assert [m["method"] for m in sent] == ["Page.enable", "Emulation.setFocusEmulationEnabled"]
    assert sent[1]["params"] == {"enabled": True}


@pytest.mark.asyncio
async def test_local_browser_connects_even_if_focus_emulation_unsupported(monkeypatch):
    import app.services.local_browser as lb

    class _Ws:
        close_code = None

        async def send(self, data):
            self._m = json.loads(data)

        async def recv(self):
            m = self._m
            if m["method"].startswith("Emulation"):
                return json.dumps({"id": m["id"], "error": {"message": "not supported"}})
            return json.dumps({"id": m["id"], "result": {}})

    async def connect(*a, **k):
        return _Ws()

    async def find(self):
        return "ws://x"

    monkeypatch.setattr(lb.websockets, "connect", connect)
    monkeypatch.setattr(lb.LocalBrowser, "_find_ws_url", find)
    b = lb.LocalBrowser("http://127.0.0.1:9222")
    await b._connect()  # 예외 없이 연결된다
    assert b._ws is not None


@pytest.mark.asyncio
async def test_local_shot_skips_identical_screens(monkeypatch):
    fake, saved = _LocalFake(same_image=True, same_screen=True), []
    monkeypatch.setattr(bt, "browser_call", fake)

    async def save(user_id, cid, img, url, title, run):
        saved.append(run)
        return True

    monkeypatch.setattr(bt, "save_local_shot", save)
    import app.services.local_browser as lb
    monkeypatch.setattr(lb, "route_for", lambda *a, **k: _coro(object()))

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1", run_tag="r1")
    await t._arun("goto", url="https://x.com")
    await t._arun("click", ref=1)  # 화면이 같다
    await t._arun("press", key="Enter")  # 같다
    assert saved == ["r1"]  # 한 장만 남긴다
    t2 = bt.BrowserActionTool(user_id="u1", run_tag="r2")  # 다른 작업은 같은 화면이어도 자기 첫 화면을 남긴다
    await t2._arun("goto", url="https://x.com")
    assert saved == ["r1", "r2"]


def test_daemon_skips_identical_screenshots():
    src = bt.DAEMON_SOURCE
    body = src[src.index("def shot(page, run):"):src.index("def settle(page):")]
    assert "hashlib.md5(raw)" in body and 'state.get("last_shot") == key' in body and "return" in body
    assert "hashlib" in src.split("SNAP_JS")[0]  # import 되어 있다


# ---- 브라우저 작업 이어받기 ----
def test_handoff_note_carries_last_screen_and_visited_urls():
    bt._HANDOFF.clear()
    assert bt.handoff_note("u1", "c1") == ""  # 이전 작업이 없으면 없다
    trail = [("https://flight.naver.com/", "홈"), ("https://flight.naver.com/", "홈"),
             ("https://flight.naver.com/flights/domestic/GMP-CJU-20261126?adult=2", "목록")]
    bt.remember_handoff("u1", "c1", trail, trail[-1][0])
    note = bt.handoff_note("u1", "c1")
    assert "이어서" in note and "GMP-CJU-20261126?adult=2" in note and "처음부터 다시 시작하지 마세요" in note
    assert note.count("https://flight.naver.com/\n") == 1 or note.count("- https://flight.naver.com/ ") == 1  # 같은 주소 반복은 접는다
    assert bt.handoff_note("u1", "c2") == "" and bt.handoff_note("u2", "c1") == ""  # 대화·사용자별
    bt._HANDOFF[("u1", "c1")]["t"] -= bt.HANDOFF_TTL_SECONDS + 1
    assert bt.handoff_note("u1", "c1") == ""  # 오래되면 쓰지 않는다
    bt.remember_handoff("u1", "c1", trail, "")
    bt.clear_handoff("u1")
    assert bt.handoff_note("u1", "c1") == ""


@pytest.mark.asyncio
async def test_next_browser_task_gets_handoff_in_its_prompt(monkeypatch):
    import types

    bt._HANDOFF.clear()
    prompts = []

    class _FakeAgent:
        def __init__(self, **kw):
            pass

        async def arun(self, prompt):
            prompts.append(prompt)
            return types.SimpleNamespace(content="완료")

    import agno.agent as agno_agent
    import app.agent.agno_engine as eng
    monkeypatch.setattr(agno_agent, "Agent", _FakeAgent)
    monkeypatch.setattr(eng, "build_agno_model", lambda *a, **k: object())
    monkeypatch.setattr(eng, "to_agno_function", lambda t: t)

    async def persist(*a, **k):
        return None

    monkeypatch.setattr(bt, "persist_profile", persist)
    tool = bt.CliBrowserAgentTool(user_id="u1", conversation_id="c9")
    await tool._arun_inner("첫 작업")
    assert "이어서" not in prompts[0]
    bt.remember_handoff("u1", "c9", [("https://x.com/a?q=1", "A")], "https://x.com/a?q=1")  # 첫 작업이 방문한 주소
    await tool._arun_inner("두 번째 작업")
    assert "이어서" in prompts[1] and "https://x.com/a?q=1" in prompts[1] and prompts[1].endswith("두 번째 작업")
    await tool._arun_inner("새 세션 작업", new_session=True)  # 새 세션은 독립
    assert "이어서" not in prompts[2]


# ---- 작업 진행 화면의 한 줄 설명 ----
DESC_EL = [
    {"ref": 31, "tag": "button", "label": "검색"},
    {"ref": 7, "tag": "input", "type": "text", "placeholder": "도시"},
    {"ref": 8, "tag": "input", "type": "password", "name": "pw"},
    {"ref": 9, "tag": "a", "label": "고객센터", "href": "https://x.com/help"},
    {"ref": 10, "tag": "select", "name": "room"},
    {"ref": 11, "tag": "input", "type": "checkbox", "label": "조식"},
    {"ref": 12, "tag": "div", "role": "tab", "label": "편도"},
    {"ref": 13, "tag": "span"},
]


def test_describe_action_is_readable():
    d = lambda a, **k: bt.describe_action(a, DESC_EL, **k)  # noqa: E731
    assert d("click", ref=31) == "클릭 · “검색” 버튼"
    assert d("click", ref=9) == "클릭 · “고객센터” 링크"
    assert d("click", ref=12) == "클릭 · “편도” 탭"
    assert d("click", ref=11) == "클릭 · “조식” 체크"
    assert d("click", ref=13) == "클릭 · 요소 #13"  # 이름도 맥락도 없는 요소
    assert d("click", ref=99) == "클릭 · 요소 99"  # 목록에 없는 ref
    assert d("type", ref=7, text="서울") == "입력 · “도시” 입력칸 ← 서울"
    assert d("type", ref=7, text="서울", submit=True).endswith("← 서울 (Enter)")
    assert d("type", ref=8, text="비밀번호123") == "입력 · “pw” 입력칸 ← ••••"  # 비밀번호는 가린다
    assert d("select", ref=10, text="더블") == "선택 · “room” 목록 → 더블"
    assert d("goto", url="https://www.flight.naver.com/flights/domestic/GMP-CJU-20261126?adult=2&fareType=Y&sort0=price:asc&x=1234567890").startswith("이동 · flight.naver.com/flights/")
    assert d("goto", url="https://x.com/").endswith("x.com/")
    assert d("press", key="Enter") == "키 입력 · Enter" and d("scroll", direction="bottom") == "스크롤 · 맨 아래로"
    assert d("wait", seconds=3) == "대기 · 3초" and d("snapshot") == "화면 읽기" and d("back") == "뒤로"
    assert d("screenshot", text="naver-flight-lowest") == "스크린샷 · naver-flight-lowest"


def test_describe_batch_summarizes_steps():
    steps = [S("type", ref=7, text="서울"), S("click", label="가는날"), S("click", ref=31)]
    out = bt.describe_batch(steps, DESC_EL)
    assert out == "일괄 3단계 · 입력 “도시” 입력칸 ← 서울 → 클릭 “가는날” → 클릭 “검색” 버튼"
    many = bt.describe_batch([S("click", ref=31)] * 6, DESC_EL)
    assert many.startswith("일괄 6단계 ·") and many.endswith("… 외 2단계")
    assert bt.describe_batch([{"action": "click", "ref": 31}], DESC_EL) == "일괄 1단계 · 클릭 “검색” 버튼"  # dict 단계도


@pytest.mark.asyncio
async def test_emitted_event_carries_readable_desc(monkeypatch):
    from app.agent import side_events

    fake = Fake()
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    q = side_events.open_channel("conv-desc")
    try:
        t = bt.BrowserActionTool(user_id="u1", conversation_id="conv-desc")
        await t._arun("snapshot")  # 요소 목록(상품 1..5, 링크)을 읽는다
        await t._arun("click", ref=3)
        evs = [q.get_nowait() for _ in range(q.qsize())]
        calls = [e for e in evs if e["type"] == "tool_call"]
        assert calls[0]["input"]["desc"] == "화면 읽기"
        assert calls[1]["input"]["desc"] == "클릭 · “상품 3” 링크" and calls[1]["input"]["ref"] == 3  # ref 는 그대로 남는다
    finally:
        side_events.close_channel("conv-desc", q)


def test_unnamed_elements_are_described_by_context():
    els = [
        {"ref": 55, "tag": "button", "label": "", "ctx": "오전 07:00 김포 → 제주 52,000원 대한항공", "cls": "btn expand"},
        {"ref": 56, "tag": "button", "label": "", "cls": "close"},
        {"ref": 57, "tag": "button", "label": "", "ctx": "대한항공 52,000원"},
    ]
    d = lambda r: bt.describe_action("click", els, ref=r)  # noqa: E731
    assert d(55) == "클릭 · “오전 07:00 김포 → 제주 52,000…” 항목의 버튼(btn expand)"
    assert d(56) == "클릭 · 버튼 #56(close)"
    assert d(57) == "클릭 · “대한항공 52,000원” 항목의 버튼"
    # 에이전트가 보는 목록에서도 무엇인지 알 수 있다
    lines = bt.compact_elements(els, "https://x.com")
    assert 'ctx="대한항공 52,000원"' in lines[2] and "cls=close" in lines[1]


def test_daemon_and_local_snapshot_collect_hints_for_unnamed_elements():
    from app.services import local_browser as lb

    for js in (bt.DAEMON_SOURCE, lb.SNAP_JS):
        assert "if (!item.label)" in js and "item.ctx" in js and "item.cls" in js and "svg title" in js


# ---- 계획 점검 (각 작업이 끝날 때마다 todo 대조) ----
def _seed(conv, steps, started=None):
    from app.tools.interaction_tools import _todo_store

    _todo_store[conv] = [{"id": str(i + 1), "content": c, "status": st} for i, (c, st) in enumerate(steps)]


def test_plan_review_note_lists_plan_and_asks_for_reconciliation():
    from app.tools.interaction_tools import _todo_store, plan_review_note

    try:
        assert plan_review_note("nope") == ""  # 계획이 없으면 없다
        _seed("c-pr", [("조회한다", "in_progress"), ("최저가순 확인한다", "pending")])
        note = plan_review_note("c-pr")
        assert "[계획 점검]" in note and "1. 조회한다 [진행 중]" in note and "2. 최저가순 확인한다 [대기]" in note
        assert "completed" in note and "합쳐" in note and "다시 위임하지 마세요" in note
        _seed("c-pr", [("조회한다", "completed"), ("확인한다", "completed")])
        assert plan_review_note("c-pr") == ""  # 모두 끝났으면 점검할 것이 없다
    finally:
        _todo_store.pop("c-pr", None)


def test_work_tools_get_plan_review_appended_before_run_tag():
    from app.agent.agno_engine import PLAN_REVIEW_TOOLS, _with_plan_review
    from app.tools.interaction_tools import _todo_store

    assert {"cli_browser_agent", "browser_parallel", "call_sub_agent"} <= PLAN_REVIEW_TOOLS
    try:
        _seed("c-pr2", [("조회한다", "in_progress"), ("확인한다", "pending")])
        out = _with_plan_review("결과 본문\n\n[browser_run:ab12cd34]", "c-pr2")
        assert out.index("[계획 점검]") < out.index("[browser_run:ab12cd34]") and out.rstrip().endswith("[browser_run:ab12cd34]")  # 태그는 맨 끝
        assert _with_plan_review("본문", "c-pr2").endswith("다시 위임하지 마세요. 남은 단계가 없으면 `todo` 를 갱신한 뒤 최종 답변을 하세요.")
        assert _with_plan_review("본문", "") == "본문"  # 대화방을 모르면 붙이지 않는다
        assert _with_plan_review("본문", "c-none") == "본문"  # 계획이 없으면 붙이지 않는다
    finally:
        _todo_store.pop("c-pr2", None)


@pytest.mark.asyncio
async def test_to_agno_function_adds_review_only_for_work_tools_and_not_on_errors():
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel

    from app.agent.agno_engine import to_agno_function
    from app.tools.interaction_tools import _todo_store

    class _In(BaseModel):
        q: str = ""

    class _Conv(StructuredTool):
        conversation_id: str = "c-pr3"

    def mk(name, result):
        async def run(q: str = "") -> str:
            return result

        return _Conv(name=name, description="d", args_schema=_In, coroutine=run)

    try:
        _seed("c-pr3", [("조회한다", "in_progress"), ("확인한다", "pending")])
        browser = await to_agno_function(mk("cli_browser_agent", "완료 보고")).entrypoint()
        assert "[계획 점검]" in browser
        failed = await to_agno_function(mk("cli_browser_agent", "Error: browser task timed out")).entrypoint()
        assert "[계획 점검]" not in failed  # 실패에는 붙이지 않는다
        other = await to_agno_function(mk("web_search", "검색 결과")).entrypoint()
        assert "[계획 점검]" not in other  # 큰 작업 단위가 아닌 도구에는 붙이지 않는다
    finally:
        _todo_store.pop("c-pr3", None)


def test_prompts_tell_to_merge_steps_and_review_after_each_task():
    from app.agent.prompts import load

    assert "한 단계로 쓰세요" in load("request_router") and "최저가순" in load("request_router")
    pc = load("plan_context")
    assert "[계획 점검]" in pc and "하나로 합쳐" in pc
    assert "[계획 점검]" in load("system")


# ---- 반복 작업 방지: 이미 된 일 건너뛰기 / 대상 기준 반복 경고 / 주소 조건 요약 ----
def cmds(t):
    return [c["cmd"] for c in t._fake.calls]


FORM = {
    "ok": True, "url": "https://x.com/search?q=a", "title": "T", "text": "본문",
    "elements": [
        {"ref": 1, "tag": "input", "type": "text", "placeholder": "어디로 떠나시나요?", "value": "Hiz Hotel Kyoto"},
        {"ref": 2, "tag": "button", "label": "2026년 11월 27일 금요일", "sel": "selected"},
        {"ref": 3, "tag": "button", "label": "2026년 11월 28일 토요일"},
        {"ref": 4, "tag": "button", "label": "추가하기 성인"},
    ],
}


@pytest.fixture
def form_tool(monkeypatch):
    fake = Fake(dict(FORM))
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    t._fake = fake
    return t


@pytest.mark.asyncio
async def test_typing_the_same_value_again_is_skipped(form_tool):
    t = form_tool
    await t._arun("snapshot")
    out = await t._arun("type", ref=1, text="Hiz Hotel Kyoto")
    assert out.startswith("[건너뜀]") and "이미 같은 값" in out and "Hiz Hotel Kyoto" in out
    assert "type" not in cmds(t)  # 브라우저로 보내지 않았다
    out2 = await t._arun("type", ref=1, text="Other Hotel")  # 다른 값은 입력한다
    assert not out2.startswith("[건너뜀]") and cmds(t).count("type") == 1
    out3 = await t._arun("type", ref=1, text="Hiz Hotel Kyoto", submit=True)  # 제출(Enter)이 필요하면 같은 값이어도 실행한다
    assert not out3.startswith("[건너뜀]") and cmds(t).count("type") == 2


@pytest.mark.asyncio
async def test_clicking_an_already_selected_item_is_skipped_once(form_tool):
    t = form_tool
    await t._arun("snapshot")
    first = await t._arun("click", ref=2)
    assert first.startswith("[건너뜀]") and "이미 선택된" in first and "click" not in cmds(t)
    again = await t._arun("click", ref=2)  # 꼭 필요하면 다시 요청해 누를 수 있다
    assert not again.startswith("[건너뜀]") and cmds(t).count("click") == 1
    other = await t._arun("click", ref=3)  # 선택되지 않은 항목은 바로 누른다
    assert not other.startswith("[건너뜀]") and cmds(t).count("click") == 2


@pytest.mark.asyncio
async def test_same_target_repeated_is_warned_even_when_refs_and_screens_change(form_tool, monkeypatch):
    t = form_tool
    await t._arun("snapshot")
    outs = []
    for i in range(4):
        # 화면이 매번 달라지고 ref 번호도 바뀌지만 같은 대상(“추가하기 성인”)이다
        page = {**FORM, "text": f"성인 {i}", "elements": [{"ref": 10 + i, "tag": "button", "label": "추가하기 성인"}]}
        t._fake.page = page
        t.last_elements = page["elements"]
        outs.append(await t._arun("click", ref=10 + i))
    assert "경고" not in outs[0] and "경고" not in outs[1]
    assert "3번째" in outs[2] and "카운터" in outs[2]  # 세 번째부터 경고 (막지는 않는다)
    assert "4번째" in outs[3] and cmds(t).count("click") == 4


def test_snapshot_exposes_selected_state():
    from app.services import local_browser as lb

    for js in (bt.DAEMON_SOURCE, lb.SNAP_JS):
        assert "aria-selected" in js and "item.sel" in js and "aria-pressed" in js
    line = bt.compact_elements([{"ref": 2, "tag": "button", "label": "27일", "sel": "selected", "pressed": True, "expanded": True}], "https://x.com")[0]
    assert line.endswith("pressed expanded selected") and "27일" in line


@pytest.mark.asyncio
async def test_goto_result_summarizes_conditions_in_the_url(form_tool):
    t = form_tool
    t._fake.page = {**FORM, "url": "https://agoda.com/ko-kr/search?textToSearch=Hiz%20Hotel%20Kyoto&checkIn=2026-11-27&adults=2&x="}
    out = await t._arun("goto", url="https://agoda.com/ko-kr/search")
    assert "[주소 조건]" in out and "checkIn=2026-11-27" in out and "adults=2" in out and "textToSearch=Hiz Hotel Kyoto" in out
    assert "x=" not in out.split("[주소 조건]")[1].split("\n")[0].replace("textToSearch", "")  # 값이 빈 파라미터는 빼고
    assert "UNTRUSTED" in out or "<<<WEB_CONTENT>>>" in out
    t._fake.page = {**FORM, "url": "https://x.com/plain"}
    assert "[주소 조건]" not in await t._arun("goto", url="https://x.com/plain")  # 조건이 없으면 붙이지 않는다
    assert "[주소 조건]" not in await t._arun("snapshot")  # goto 에만


def test_prompt_tells_not_to_repeat_work():
    from app.agent.prompts import load

    p = load("browser_agent")
    assert "[주소 조건]" in p and "[건너뜀]" in p and "selected" in p and "다시 조작하지 마세요" in p


# ---- 스냅샷 확대 / 맥락 개선 / 커스텀 드롭다운 선택 ----
def test_snapshot_script_is_shared_and_covers_custom_widgets():
    from app.services import local_browser as lb
    from app.services.browser_snapshot import SNAP_JS

    assert lb.SNAP_JS is SNAP_JS and SNAP_JS in bt.DAEMON_SOURCE  # 데몬과 로컬이 같은 스크립트
    for token in ("[role=option]", "[role=radio]", "[role=switch]", "[role=combobox]", "cursor", "overlaySel", "data-testid", "data-selenium", "STOP"):
        assert token in SNAP_JS, token
    assert "closest('li,tr,[role=row],[role=listitem],article,section,form,dl')" not in SNAP_JS  # 큰 영역의 첫 글자를 맥락으로 쓰던 방식은 없앴다


def test_unnamed_buttons_with_same_context_are_told_apart():
    els = [
        {"ref": 1, "tag": "button", "label": "", "tid": "child-age-0", "ctx": "첫째 아동 나이"},
        {"ref": 2, "tag": "button", "label": "", "tid": "child-age-1", "ctx": "둘째 아동 나이"},
        {"ref": 3, "tag": "button", "label": "", "ctx": "나이", "cls": "age"},
        {"ref": 4, "tag": "button", "label": "", "ctx": "나이", "cls": "age"},  # 모양까지 같은 쌍둥이
    ]
    assert bt.target_identity(els[0], els) != bt.target_identity(els[1], els)
    assert bt.target_identity(els[2], els) != bt.target_identity(els[3], els)  # 순번으로 구분
    assert bt.target_identity(els[2], els)[-1] == 1 and bt.target_identity(els[3], els)[-1] == 2
    assert bt.describe_action("click", els, ref=1) == "클릭 · “첫째 아동 나이” 항목의 버튼[child-age-0]"
    assert 'tid="child-age-1"' in bt.compact_elements(els, "https://x.com")[1]
    opt = [{"ref": 9, "tag": "li", "label": "8세", "role": "option"}]
    assert bt.describe_action("click", opt, ref=9) == "클릭 · “8세” 항목"


class Dropdown:
    """여는 버튼을 누르면 항목이 나타나는 가짜 사이트."""

    def __init__(self, with_options=True):
        self.calls = []
        self.open = False
        self.with_options = with_options
        self.chosen = None

    def screen(self):
        els = [{"ref": 1, "tag": "button", "label": "", "tid": "age-0", "ctx": "첫째 아동 나이"}]
        if self.open and self.with_options:
            els += [{"ref": 2, "tag": "li", "label": "7세"}, {"ref": 3, "tag": "li", "label": "8세"}]
        return {"ok": True, "url": "https://x.com/", "title": "T", "elements": els, "text": f"열림={self.open} 선택={self.chosen}"}

    async def __call__(self, user_id, payload, **kw):
        self.calls.append((payload["cmd"], payload.get("ref")))
        if payload["cmd"] == "click":
            if payload["ref"] == 1:
                self.open = not self.open
            elif payload["ref"] == 3:
                self.chosen, self.open = "8세", False
        return self.screen()


@pytest.mark.asyncio
async def test_select_on_custom_dropdown_opens_then_picks_the_option(monkeypatch):
    dd = Dropdown()
    monkeypatch.setattr(bt, "browser_call", dd)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    await t._arun("snapshot")
    out = await t._arun("select", ref=1, text="8세")
    assert out.startswith("[드롭다운에서 “8세” 선택]")
    assert [c for c in dd.calls if c[0] == "click"] == [("click", 1), ("click", 3)]  # 열고 → 항목 클릭
    assert dd.chosen == "8세"


@pytest.mark.asyncio
async def test_select_on_custom_dropdown_reports_visible_options_when_missing(monkeypatch):
    dd = Dropdown()
    monkeypatch.setattr(bt, "browser_call", dd)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    await t._arun("snapshot")
    out = await t._arun("select", ref=1, text="99세")
    assert out.startswith("Error") and "7세" in out and "8세" in out and dd.chosen is None
    # 항목이 요소로 잡히지 않는 사이트: 반복해서 열고 닫지 말고 다른 방법을 쓰게 안내한다
    dd2 = Dropdown(with_options=False)
    monkeypatch.setattr(bt, "browser_call", dd2)
    t2 = bt.BrowserActionTool(user_id="u1")
    await t2._arun("snapshot")
    out2 = await t2._arun("select", ref=1, text="8세")
    assert out2.startswith("Error") and "ArrowDown" in out2 and "주소 파라미터" in out2


@pytest.mark.asyncio
async def test_native_select_is_not_treated_as_custom(monkeypatch):
    fake = Fake({"ok": True, "url": PAGE, "title": "T", "text": "t", "elements": [{"ref": 1, "tag": "select", "label": "", "name": "room"}]})
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    await t._arun("snapshot")
    await t._arun("select", ref=1, text="d")
    assert [c["cmd"] for c in fake.calls] == ["snapshot", "select"]  # <select> 는 그대로 select 명령


# ---- 취소선 표시 / 가격 비교 지침 / 임의 조건 금지 ----
def test_snapshot_script_marks_struck_through_text():
    from app.services.browser_snapshot import SNAP_JS

    for token in ("line-through", "'DEL'", "'STRIKE'", "'S'", "~~"):
        assert token in SNAP_JS, token
    assert SNAP_JS in bt.DAEMON_SOURCE  # 로컬 브라우저와 같은 스크립트


def test_format_explains_struck_text_only_when_present():
    res = {"ok": True, "url": "https://x.com", "title": "T", "elements": [], "text": "와이페이모어 ~~193,800원~~ 143,800원"}
    out = bt._format(res)
    assert "~~193,800원~~" in out and "취소선이 그어진 글자" in out and "현재 가격이 아닙니다" in out
    assert "취소선" not in bt._format({**res, "text": "트립닷컴 187,600원"})  # 없으면 안내도 없다


def test_prompts_require_full_price_comparison_and_no_invented_conditions():
    from app.agent.prompts import load

    b = load("browser_agent")
    assert "첫 행만" in b and "~~글자~~" in b and "조건이 붙은 할인가" in b and "1인 가격 × 인원" in b and "검산" in b
    t = load("team_default")
    assert "말하지 않은 조건" in t and "임의로 넣지 마세요" in t and "가정" in t and "첫 행으로 단정" in t


# ---- 로컬 브라우저 스크린샷 저장소 (sandbox 와 무관) ----
@pytest.fixture
def shots_dir(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "LOCAL_SHOTS_DIR", str(tmp_path / "shots"))
    return tmp_path / "shots"


@pytest.mark.asyncio
async def test_local_shot_is_saved_without_any_sandbox(shots_dir):
    import base64

    from app.services import local_shots

    ok = await bt.save_local_shot("u1", "conv1", base64.b64encode(b"JPEGDATA").decode(), "https://x.com/a", "제목", "run1")
    assert ok
    rows = local_shots.rows("u1")
    assert len(rows) == 1 and rows[0]["run"] == "run1" and rows[0]["url"] == "https://x.com/a" and rows[0]["title"] == "제목"
    assert rows[0]["f"].startswith("local://")
    p = local_shots.image_path("u1", rows[0]["f"][len("local://"):])
    assert p is not None and p.read_bytes() == b"JPEGDATA"
    assert local_shots.rows("u2") == []  # 다른 사용자 것은 보이지 않는다


def test_local_shots_keep_only_latest_and_remove_old_files(shots_dir):
    from app.services import local_shots

    for i in range(local_shots.MAX_SHOTS + 4):
        local_shots.save("u1", f"img{i}".encode(), "https://x.com", "t", "r")
    rows = local_shots.rows("u1")
    assert len(rows) == local_shots.MAX_SHOTS
    jpgs = [f for f in (shots_dir / "u1").iterdir() if f.suffix == ".jpg"]
    assert len(jpgs) == local_shots.MAX_SHOTS  # 밀려난 이미지 파일도 지웠다
    assert (local_shots.image_path("u1", rows[-1]["f"][8:])).read_bytes() == f"img{local_shots.MAX_SHOTS + 3}".encode()


def test_local_shot_image_path_rejects_path_tricks(shots_dir):
    from app.services import local_shots

    local_shots.save("u1", b"x", "u", "t", None)
    for bad in ("../u2/1234567890123.jpg", "index.jsonl", "..", "1234567890123.png", "", "a/b.jpg", "1234567890123.jpg/../../x"):
        assert local_shots.image_path("u1", bad) is None


@pytest.mark.asyncio
async def test_shots_api_returns_local_shots_even_when_sandbox_is_stopped(shots_dir, monkeypatch):
    from types import SimpleNamespace

    import app.api.browser as api
    from app.services import local_shots
    from app.services import sandbox_service as ss

    local_shots.save("u1", b"a", "https://x.com/1", "첫째", "runA")
    local_shots.save("u1", b"b", "https://x.com/2", "둘째", "runA")
    local_shots.save("u1", b"c", "https://x.com/3", "셋째", "runB")

    async def scope(cid, uid, db):
        return cid

    async def stopped(user_id, db, conv=None):
        return SimpleNamespace(status="stopped", container_id="c1")  # sandbox 꺼짐

    monkeypatch.setattr(api, "resolve_scope", scope)
    monkeypatch.setattr(ss.SandboxService, "get_sandbox", staticmethod(stopped))
    user = SimpleNamespace(id="u1")
    latest = await api.list_shots(conversation_id=None, run="latest", limit=30, current_user=user, db=None)
    assert [r.title for r in latest] == ["셋째"] and latest[0].path.startswith("local://")  # 가장 최근 작업
    a = await api.list_shots(conversation_id=None, run="runA", limit=30, current_user=user, db=None)
    assert [r.title for r in a] == ["첫째", "둘째"]
    assert await api.list_shots(conversation_id=None, run="none", limit=30, current_user=user, db=None) == []
    assert await api.list_shots(conversation_id=None, run="latest", limit=30, current_user=SimpleNamespace(id="u2"), db=None) == []


@pytest.mark.asyncio
async def test_shot_image_endpoint_serves_own_files_only(shots_dir):
    from types import SimpleNamespace

    import app.api.browser as api
    from app.services import local_shots
    from fastapi import HTTPException

    path = local_shots.save("u1", b"JPG", "u", "t", None)
    name = path[len("local://"):]
    res = await api.shot_image(name=name, current_user=SimpleNamespace(id="u1"))
    assert res.media_type == "image/jpeg" and str(res.path).endswith(name)
    with pytest.raises(HTTPException) as e:
        await api.shot_image(name=name, current_user=SimpleNamespace(id="u2"))  # 다른 사용자는 못 본다
    assert e.value.status_code == 404
    with pytest.raises(HTTPException):
        await api.shot_image(name="../u1/" + name, current_user=SimpleNamespace(id="u1"))


# ---- 스크린샷 중복: 화면 내용 기준 ----
def _b(text, url=PAGE, sy=0):
    return bt.screen_basis_of({"ok": True, "url": url, "text": text, "sy": sy})


def test_same_screen_tolerates_small_changes_but_not_real_ones():
    base = "\n".join(f"상품 {i} 가격 {i * 1000}원" for i in range(40)) + "\n배너 3 / 6"
    assert bt.same_screen(_b(base), _b(base.replace("3 / 6", "4 / 6")))  # 회전 배너 카운터 하나가 바뀐 정도는 같은 화면 (1/41줄)
    assert not bt.same_screen(_b(base), _b("\n".join(f"다른 {i}" for i in range(40))))  # 내용이 바뀌면 다른 화면
    assert not bt.same_screen(_b(base), _b(base, url="https://shop.example.com/other"))  # 주소가 다르면 다른 화면
    assert not bt.same_screen(_b(base, sy=0), _b(base, sy=2))  # 스크롤 위치가 반 화면 이상 바뀌면 다른 화면(보이는 영역이 다르다)
    assert not bt.same_screen(None, _b(base)) and bt.screen_basis_of({"ok": False}) is None


@pytest.mark.asyncio
async def test_local_shots_skip_near_duplicates_but_keep_real_changes(monkeypatch):
    saved = []

    class Page:
        def __init__(self):
            self.text, self.url, self.sy, self.n = "", PAGE, 0, 0

        async def __call__(self, user_id, payload, **kw):
            if payload["cmd"] == "frame":
                self.n += 1
                return {"ok": True, "img": f"img{self.n}", "url": self.url, "title": "T"}  # 이미지는 매번 다르다(픽셀 차이)
            return {"ok": True, "url": self.url, "title": "T", "elements": _els(2), "text": self.text, "sy": self.sy}

    page = Page()
    monkeypatch.setattr(bt, "browser_call", page)

    async def save(user_id, cid, img, url, title, run):
        saved.append((run, url, page.sy))
        return True

    monkeypatch.setattr(bt, "save_local_shot", save)
    import app.services.local_browser as lb
    monkeypatch.setattr(lb, "route_for", lambda *a, **k: _coro(object()))

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1", run_tag="r1")
    body = "\n".join(f"항공편 {i} {i * 1000}원" for i in range(30))
    page.text = body + "\n배너 1 / 6"
    await t._arun("click", ref=1)  # 1: 첫 화면
    page.text = body + "\n배너 2 / 6"
    await t._arun("click", ref=1)  # 배너만 바뀜 → 중복
    await t._arun("press", key="Enter")  # 그대로 → 중복
    assert len(saved) == 1
    page.sy = 2
    await t._arun("scroll", direction="down")  # 스크롤로 보이는 영역이 바뀜 → 2: 새 화면
    assert len(saved) == 2
    page.sy = 0
    await t._arun("scroll", direction="top")  # 다시 처음 화면: 최근 3장 중 하나와 같다 → 중복
    assert len(saved) == 2
    page.text, page.url = "\n".join(f"상세 {i}" for i in range(30)), "https://shop.example.com/detail"
    await t._arun("click", ref=1)  # 3: 다른 페이지
    assert len(saved) == 3
    t2 = bt.BrowserActionTool(user_id="u1", run_tag="r2")  # 다른 작업은 같은 화면이어도 자기 첫 화면을 남긴다
    await t2._arun("click", ref=1)
    assert len(saved) == 4 and saved[-1][0] == "r2"


def test_daemon_dedupes_by_screen_content():
    src = bt.DAEMON_SOURCE
    body = src[src.index("def screen_basis(page):"):src.index("def settle(page):")]
    assert "def same_screen(a, b):" in body and "0.9" in body and "recent_shots" in body and "del recent[:-3]" in body
    assert "scrollY" in body and "innerText" in body


def test_progress_screenshots_use_quality_70_but_live_frames_keep_55():
    src = bt.DAEMON_SOURCE
    shot_fn = src[src.index("def shot(page, run):"):src.index("def settle(page):")]
    assert 'page.screenshot(type="jpeg", quality=70)' in shot_fn  # sandbox 스크린샷
    assert bt.SHOT_QUALITY == 70
    live = src[src.index('if cmd == "frame":'):src.index('if cmd == "mouse":')]
    assert 'c.get("quality") or 55' in live  # 라이브 화면 전송은 대역폭을 위해 그대로


# ---- 로컬 브라우저 스크린샷: 페이지 원래 폭으로 캡처 (앱은 zoom 으로 축소해 보여 준다) ----
class _CdpFake:
    """CDP 호출을 기록하는 가짜 (LocalBrowser._send / _eval 대체)."""

    def __init__(self, metrics, dpr=1.0):
        self.metrics = metrics
        self.dpr = dpr
        self.sent = []

    async def send(self, method, params=None, timeout=30.0):
        self.sent.append((method, params))
        if method == "Page.getLayoutMetrics":
            if isinstance(self.metrics, Exception):
                raise self.metrics
            return self.metrics
        return {"data": "QUJD"}

    async def ev(self, expression, timeout=15.0):
        if "devicePixelRatio" in expression:
            return self.dpr
        return "https://x.com/" if "href" in expression else "T"


def _lb(monkeypatch, metrics, dpr=1.0):
    import app.services.local_browser as lb

    fake = _CdpFake(metrics, dpr)
    b = lb.LocalBrowser("http://127.0.0.1:9222")
    monkeypatch.setattr(b, "_send", fake.send)
    monkeypatch.setattr(b, "_eval", fake.ev)
    return b, fake


def _metrics(css_w, css_h, zoom, page_x=0, page_y=0):
    return {"cssVisualViewport": {"clientWidth": css_w, "clientHeight": css_h, "pageX": page_x, "pageY": page_y},
            "visualViewport": {"zoom": zoom}}


async def _clip(b, fake):
    res = await b._dispatch("frame", {"quality": 70})
    assert res["ok"] and res["img"] == "QUJD"
    cap = next(p for m, p in fake.sent if m == "Page.captureScreenshot")
    assert cap["format"] == "jpeg" and cap["quality"] == 70
    return cap.get("clip")


@pytest.mark.asyncio
async def test_clip_uses_zoomed_visible_area_not_css_size(monkeypatch):
    # 앱 창 709px 에 1280px 페이지를 zoom 0.554 로 축소, 화면 배율 1 (사용자의 기본 캡처가 709px 이던 환경)
    b, fake = _lb(monkeypatch, _metrics(1280, 1588, 0.554), dpr=0.554)
    clip = await _clip(b, fake)
    assert round(clip["width"]) == 709 and round(clip["height"]) == 880  # 보이는 영역(CSS 1280 이 아니다: 그러면 배경만 넓어진다)
    assert round(clip["width"] * clip["scale"]) == 1280  # 결과 가로가 페이지 원래 폭
    assert 1.7 < clip["scale"] < 1.9 and clip["x"] == 0 and clip["y"] == 0


@pytest.mark.asyncio
async def test_clip_does_not_shrink_below_default_on_retina(monkeypatch):
    # 화면 배율 2: 기본 캡처가 이미 1388px 이라 더 작게(1280) 만들지 않는다 (scale 1)
    b, fake = _lb(monkeypatch, _metrics(1252.7, 1537.9, 0.554), dpr=1.108)
    clip = await _clip(b, fake)
    assert clip["scale"] == 1.0 and round(clip["width"]) == 694 and round(clip["height"]) == 852


@pytest.mark.asyncio
async def test_clip_scroll_offset_is_converted_to_the_same_unit(monkeypatch):
    b, fake = _lb(monkeypatch, _metrics(1280, 1588, 0.5, page_x=0, page_y=1500), dpr=0.5)
    clip = await _clip(b, fake)
    assert clip["y"] == 750 and clip["x"] == 0  # 문서 위치 1500 CSS px × zoom 0.5


@pytest.mark.asyncio
async def test_clip_is_capped_for_very_large_views_and_without_zoom(monkeypatch):
    b, fake = _lb(monkeypatch, _metrics(3200, 1800, 1.0), dpr=1.0)  # 줌 없음, 매우 큰 창
    clip = await _clip(b, fake)
    assert clip["scale"] == 0.5 and clip["width"] * clip["scale"] == 1600  # 가로 상한 1600px
    b2, fake2 = _lb(monkeypatch, _metrics(1280, 800, 1.0), dpr=1.0)  # 줌 없음: 기본과 같은 크기
    assert (await _clip(b2, fake2))["scale"] == 1.0
    b3, fake3 = _lb(monkeypatch, _metrics(1280, 8000, 1.0), dpr=1.0)  # 세로 상한 3000px
    assert round((await _clip(b3, fake3))["height"] * (await _clip(b3, fake3))["scale"]) == 3000


@pytest.mark.asyncio
async def test_clip_falls_back_to_default_capture_when_unmeasurable(monkeypatch):
    import app.services.local_browser as lb

    b, fake = _lb(monkeypatch, lb.LocalBrowserError("지원 안 함"))
    assert await _clip(b, fake) is None
    b2, fake2 = _lb(monkeypatch, {"cssVisualViewport": {"clientWidth": 0, "clientHeight": 0}})
    assert await _clip(b2, fake2) is None


@pytest.mark.asyncio
async def test_local_shot_does_not_stall_the_task_when_capture_hangs(monkeypatch):
    saved = []

    async def hanging(user_id, payload, **kw):
        if payload["cmd"] == "frame":
            await asyncio.sleep(60)  # 창이 숨겨져 캡처가 응답하지 않는 상황
        return {"ok": True, "url": PAGE, "title": "T", "elements": _els(2), "text": "\n".join(f"줄 {i}" for i in range(20)), "sy": 0}

    monkeypatch.setattr(bt, "browser_call", hanging)
    monkeypatch.setattr(bt, "SHOT_CAPTURE_TIMEOUT", 0.2)

    async def save(*a, **k):
        saved.append(1)
        return True

    monkeypatch.setattr(bt, "save_local_shot", save)
    import app.services.local_browser as lb
    monkeypatch.setattr(lb, "route_for", lambda *a, **k: _coro(object()))

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1", run_tag="r1")
    started = asyncio.get_running_loop().time()
    out = await t._arun("click", ref=1)
    assert out.startswith("URL:") or "화면 변화" in out  # 동작 결과는 정상으로 돌아온다
    assert asyncio.get_running_loop().time() - started < 3 and saved == []  # 스크린샷은 포기하고 작업은 지연되지 않았다


def test_snapshot_over_cap_keeps_controls_and_new_elements_before_links():
    """링크가 수백 개인 목록 화면에서도 조작 요소(버튼·입력칸)와 방금 열린 패널의 요소가 상한에 밀려 잘리지 않는다."""
    from app.services.browser_snapshot import SNAP_JS

    assert "window.__agentSeen" in SNAP_JS and "added.length <= 40" in SNAP_JS  # 방금 나타난 요소는 소수일 때만 앞에 둔다
    assert "const rank" in SNAP_JS and "el.tagName === 'A' && !btnLike(el)" in SNAP_JS  # 화면 안에서는 버튼·입력칸(버튼 모양 링크 포함) → 링크 → 일반 요소 순
    assert "btnLike" in SNAP_JS and "(btn|button|tab)" in SNAP_JS  # <a class="btn"> 탭(메가박스 '극장별')이 포스터 버튼에 밀려 잘리지 않는다
    order = SNAP_JS.index("cands.filter(el => isPop.has(el))")
    assert order < SNAP_JS.index("g[0].has(el)") < SNAP_JS.index("g[1].has(el)") < SNAP_JS.index("g[2].has(el)")


def test_snapshot_text_falls_back_to_visible_text_for_long_pages():
    """본문이 길면 앞 3000자 대신 지금 화면에 보이는 글자를 본문으로 쓴다 (왼쪽 필터가 앞부분을 차지하는 목록 화면)."""
    from app.services.browser_snapshot import SNAP_JS

    assert "txt.length > 2800" in SNAP_JS and "createTreeWalker" in SNAP_JS and "window.innerHeight" in SNAP_JS


def test_sandbox_daemon_launches_new_headless_chromium():
    """sandbox 데몬은 new headless(channel=chromium)로 브라우저를 띄운다 (기본 old headless shell 은 일부 사이트가 일반 접속도 막는다)."""
    assert 'channel="chromium"' in bt.DAEMON_SOURCE and "headless=True" in bt.DAEMON_SOURCE


def test_sandbox_daemon_drops_headless_marker_from_user_agent():
    """User-Agent 의 'HeadlessChrome' 표기만 'Chrome' 으로 바꾼다 (버전·OS 는 브라우저가 알려 준 실제 값)."""
    assert 'replace("HeadlessChrome", "Chrome")' in bt.DAEMON_SOURCE and '_ctx_args["user_agent"]' in bt.DAEMON_SOURCE


def _ref_tool(monkeypatch, old_page, handler):
    fake = Fake(old_page)
    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    return t, fake


@pytest.mark.asyncio
async def test_missing_ref_is_auto_healed_when_same_element_is_unique_on_same_page(monkeypatch):
    """화면은 그대로인데 번호만 바뀐 경우: 같은 요소(정체가 하나)를 최신 번호로 한 번 다시 실행한다."""
    old_page = {"ok": True, "url": PAGE, "title": "T", "elements": [{"ref": 47, "tag": "button", "label": "검색"}, {"ref": 48, "tag": "a", "label": "홈", "href": "/"}], "text": "본문"}
    t, _ = _ref_tool(monkeypatch, old_page, None)
    await t._arun("snapshot")
    new_els = [{"ref": 3, "tag": "button", "label": "검색"}, {"ref": 4, "tag": "a", "label": "홈", "href": "/"}]
    clicked = []

    async def flaky(user_id, payload, **kw):
        if payload["cmd"] == "click":
            clicked.append(payload["ref"])
            return {"ok": False, "error": "ref 47 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요"} if payload["ref"] == 47 else {"ok": True, "url": PAGE, "title": "T", "elements": new_els, "text": "다음 화면"}
        return {"ok": True, "url": PAGE, "title": "T", "elements": new_els, "text": "본문"}

    monkeypatch.setattr(bt, "browser_call", flaky)
    out = await t._arun("click", ref=47)
    assert clicked == [47, 3]  # 처음 번호로 실패 → 최신 번호로 한 번 다시
    assert out.startswith("[자동 복구]") and "[47] 대신 최신 번호로 같은 요소 [3] button “검색”" in out and "Error" not in out.split("\n")[0]


@pytest.mark.asyncio
async def test_missing_ref_error_explains_cause_when_it_cannot_be_healed(monkeypatch):
    """복구할 수 없으면(같은 이름이 여럿·사라짐·화면 이동) 무엇을 누르려 했는지·원인·최신 요소 목록을 함께 돌려준다."""
    old_page = {"ok": True, "url": PAGE, "title": "T", "elements": [{"ref": 47, "tag": "button", "label": "검색"}, {"ref": 48, "tag": "a", "label": "홈", "href": "/"}], "text": "본문"}
    t, _ = _ref_tool(monkeypatch, old_page, None)
    await t._arun("snapshot")
    new_els = [{"ref": 3, "tag": "a", "label": "홈", "href": "/"}]  # '검색' 버튼이 사라졌다
    clicked = []

    async def flaky(user_id, payload, **kw):
        if payload["cmd"] == "click":
            clicked.append(payload["ref"])
            return {"ok": False, "error": "ref 47 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요"}
        return {"ok": True, "url": PAGE, "title": "T", "elements": new_els, "text": "본문"}

    monkeypatch.setattr(bt, "browser_call", flaky)
    out = await t._arun("click", ref=47)
    assert clicked == [47]  # 다시 실행하지 않는다
    assert out.splitlines()[0].startswith("Error: ref 47 요소를 찾을 수 없습니다")  # 첫 줄은 기존 문구 그대로
    assert '[누르려던 요소] [47] button "검색"' in out and "사라졌습니다" in out and '[3] a "홈"' in out  # 최신 목록 포함
    assert t.last_elements == new_els  # 다음 동작은 최신 번호를 쓴다


def test_heal_candidate_requires_same_page_unique_identity():
    old = {"ref": 5, "tag": "button", "label": "확인"}
    els = [{"ref": 1, "tag": "button", "label": "확인"}]
    assert bt._heal_candidate(old, [old], els, "https://x.com/a", "https://x.com/a#top")["ref"] == 1
    assert bt._heal_candidate(old, [old], els, "https://x.com/a", "https://x.com/b") is None  # 화면 이동: 다른 화면의 같은 이름일 수 있다
    assert bt._heal_candidate(old, [old], els + [{"ref": 2, "tag": "button", "label": "확인"}], "https://x.com/a", "https://x.com/a") is None  # 같은 요소가 여럿이면 정할 수 없다
    assert bt._heal_candidate({"ref": 5, "tag": "button"}, [{"ref": 5, "tag": "button"}], [{"ref": 1, "tag": "button"}], "https://x.com/a", "https://x.com/a") is None  # 이름도 맥락도 없는 요소


def test_ref_missing_detects_local_and_sandbox_errors():
    assert bt._ref_missing("ref 47 요소를 찾을 수 없습니다. snapshot 으로 최신 ref 를 확인하세요")
    assert bt._ref_missing('Locator.click: Timeout 8000ms exceeded. waiting for locator("[data-agent-ref=\\"47\\"]")')
    assert not bt._ref_missing("net::ERR_CONNECTION_RESET") and not bt._ref_missing(None)


def test_error_brief_keeps_cause_and_first_elements_only():
    full = ("Error: ref 47 요소를 찾을 수 없습니다.\n[누르려던 요소] [47] button \"검색\"\n[원인] 화면이 이동했습니다.\n[조치] 다시 고르세요.\n\n"
            "URL: https://x.com/\nTitle: T\nInteractive elements (...):\n<<<WEB_CONTENT>>>\n" + "\n".join(f"[{i}] a \"링크{i}\"" for i in range(100)) + "\n<<<END_WEB_CONTENT>>>\nPage text ...")
    brief = bt._error_brief(full)
    assert brief.startswith("Error: ref 47") and "[원인] 화면이 이동했습니다." in brief
    assert "앞 40개 / 전체 100개" in brief and '[39] a "링크39"' in brief and '[40] a "링크40"' not in brief and "Page text" not in brief


def test_batch_validation_error_explains_problem_reason_and_fix():
    steps = [S("type", ref=1, text="서울"), S("press", key="Enter"), S("click", ref=3)]
    els = [{"ref": 1, "tag": "input", "label": "도시"}, {"ref": 3, "tag": "button", "label": "확인"}]
    msg = bt.validate_batch(steps, els)
    first = msg.splitlines()[0]
    assert first.startswith("Error: 일괄 동작을 실행하지 않았습니다") and "3번째 단계" in first and "2번째 단계" in first and len(first) < 200  # 첫 줄만 봐도 요지를 안다
    for part in ("[문제]", "[이유]", "[조치]", "[요청된 단계]", "label"):
        assert part in msg
    assert "← 화면이 바뀔 수 있는 단계" in msg and "← 여기서 중단" in msg and "입력" in msg and "“확인” 버튼" in msg
    mid = bt.validate_batch([S("click", ref=3), S("type", ref=1, text="x")], els)
    assert "ref 가 무효" in mid  # 중간의 ref 클릭 자체는 허용되고, 그 뒤의 ref 단계만 무효가 된다
    assert bt.validate_batch([S("type", ref=1, text="x"), S("click", ref=3)], els) is None  # 클릭이 마지막이면 문제없다
    assert "ref 또는 label" in bt.validate_batch([S("type", text="a")])


def test_convert_ref_steps_turns_invalidated_refs_into_labels():
    els = [{"ref": 1, "tag": "input", "label": "출발지"}, {"ref": 2, "tag": "button", "label": "검색"}, {"ref": 3, "tag": "button", "label": "더보기"}, {"ref": 4, "tag": "button", "label": "더보기"}, {"ref": 5, "tag": "button"}]
    steps = [S("type", ref=1, text="ICN"), S("click", ref=2), S("click", ref=4), S("click", ref=5)]
    out, notes = bt.convert_ref_steps(steps, els)
    assert out[0].ref == 1 and out[1].ref == 2  # 처음 화면 기준으로 유효한 단계(첫 단계, 첫 클릭 자신)는 그대로
    assert out[2].ref is None and out[2].label == "더보기" and out[2].nth == 2  # 같은 이름이 둘이면 몇 번째인지 보존
    assert out[3].ref == 5 and len(notes) == 1 and "“더보기”" in notes[0]  # 이름 없는 요소는 바꿀 수 없다
    assert "ref 가 무효" in bt.validate_batch(out, els)  # 바꿀 수 없는 단계는 설명과 함께 거부된다
    ok = [out[0], out[1], out[2]]
    assert bt.validate_batch(ok, els) is None


@pytest.mark.asyncio
async def test_batch_with_ref_after_screen_change_runs_by_label_instead_of_being_rejected(monkeypatch):
    """클릭 뒤에 이어지는 ref 단계는 거부하지 않고, 이름으로 바꿔 화면을 다시 읽은 뒤 실행한다."""
    page1 = {"ok": True, "url": PAGE, "title": "T", "elements": [{"ref": 1, "tag": "button", "label": "열기"}, {"ref": 2, "tag": "input", "label": "도시"}], "text": "본문"}
    page2 = {"ok": True, "url": PAGE, "title": "T", "elements": [{"ref": 7, "tag": "input", "label": "도시"}, {"ref": 8, "tag": "button", "label": "확인"}], "text": "열림"}
    calls = []
    state = {"after_click": False}

    async def fake(user_id, payload, **kw):
        calls.append(payload)
        if payload["cmd"] == "click" and payload.get("ref") == 1:
            state["after_click"] = True
        return dict(page2 if state["after_click"] else page1)

    monkeypatch.setattr(bt, "browser_call", fake)

    async def no_policy(self):
        return False

    monkeypatch.setattr(bt.BrowserActionTool, "_needs_policy", no_policy)
    t = bt.BrowserActionTool(user_id="u1")
    await t._arun("snapshot")
    out = await t._arun("batch", steps=[{"action": "click", "ref": 1}, {"action": "type", "ref": 2, "text": "서울"}])
    assert not out.startswith("Error") and "[자동 변환]" in out and "“도시”" in out
    typed = [c for c in calls if c["cmd"] == "type"]
    assert len(typed) == 1 and typed[0]["ref"] == 7  # 처음 번호(2)가 아니라 다시 읽은 화면의 번호(7)로 입력했다


def test_same_named_elements_are_told_apart_by_order_and_area():
    """슬라이더마다 있는 'Next' 처럼 이름이 같은 요소가 여럿이면 순번(2/2)과 구역 이름을 보여 줘서 엉뚱한 쪽이 눌리지 않게 한다."""
    from app.tools import browser_tools as bt
    from app.services import browser_snapshot as bs, local_browser as lb

    month = {"ref": 3, "tag": "button", "label": "Next", "dup": "1/2", "ctx": "달력"}
    time_ = {"ref": 118, "tag": "button", "label": "Next", "dup": "2/2", "ctx": "시간선택"}
    assert '(1/2 · "달력")' in bt._compact_element(month) and '(2/2 · "시간선택")' in bt._compact_element(time_)
    assert bt.describe_action("click", [month, time_], ref=118).endswith("(2/2)")
    assert "byLabel" in bs.SNAP_JS and "it.dup" in bs.SNAP_JS and "covered" in bs.SNAP_JS  # 이름이 같은 요소 구분, 가려진 요소는 뒤로
    import inspect
    assert "BLOCKED_JS" in inspect.getsource(lb.LocalBrowser._element_center) and "elementFromPoint" in bs.BLOCKED_JS  # 보이지 않는 자리를 눌러 다른 곳이 눌리는 것을 막는다
    assert "BLOCKED_JS" in bt.DAEMON_SOURCE and "elementFromPoint" in bt.DAEMON_SOURCE and "sig" in bt.DAEMON_SOURCE  # sandbox 데몬도 같다


def test_sandbox_browser_runs_in_korea_time():
    """컨테이너 시간대는 UTC 다. 한국 사이트가 브라우저 시각으로 '지금'을 계산하므로(코레일 시각 칩이 9시간 밀려 선택됨) 시간대를 서울로 맞춘다."""
    from app.tools import browser_tools as bt

    assert 'timezone_id="Asia/Seoul"' in bt.DAEMON_SOURCE and 'locale="ko-KR"' in bt.DAEMON_SOURCE


def test_calendar_cells_show_their_date_and_big_repeated_lists_do_not_push_out_popup_buttons():
    """달력 칸은 이름이 '4' 뿐이어도 날짜(data-iso)를 보여 주고, 같은 모양이 40개를 넘는 목록(터미널 수백 개)은 팝업의 '선택완료'·'확인' 버튼 뒤로 간다."""
    from app.services.browser_snapshot import SNAP_JS

    assert "data-iso" in SNAP_JS and "item.date" in SNAP_JS
    assert "bulk" in SNAP_JS and "groupCount" in SNAP_JS and "> 40" in SNAP_JS
    assert "date=2026-12-04" in bt._compact_element({"ref": 7, "tag": "div", "role": "gridcell", "label": "4", "date": "2026-12-04"})

"""사이트별 요령 리소스: 파일 형식, 매칭, 이동 시 한 번만 주입."""
import re
from datetime import date

import pytest

from app.agent import prompts, site_tips
from app.tools import browser_tools as bt


def test_every_tip_file_is_well_formed_and_domains_are_unique():
    tips = site_tips.all_tips()
    assert len(tips) >= 4
    seen: dict[str, str] = {}
    for t in tips:
        assert t.name and t.domains and t.body, t
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", t.verified) and date.fromisoformat(t.verified), f"{t.name}: verified 날짜 형식"
        for d in t.domains:
            assert d not in seen, f"도메인 중복: {d} ({seen[d]} / {t.name})"
            seen[d] = t.name
        assert "{" not in t.body  # 자리표시자는 '검색어' 문구를 쓴다 (포맷 문자열 오해 방지)


def test_prompt_no_longer_embeds_site_specific_facts():
    text = "\n".join(prompts.sections("browser_agent"))
    for marker in ("danawa", "priceASC", "gmarket", "enuri"):
        assert marker not in text  # 사이트 사실은 site_tips/ 로 옮겼다
    assert "사이트 요령" in text  # 프롬프트에는 '주어지면 따른다'는 규칙만 남는다


def test_match_by_url_text_and_alias():
    names = lambda task, url=None: {t.name for t in site_tips.match_task(task, url)}
    assert names("가격 확인", "https://search.danawa.com/dsearch.php?query=a") == {"다나와"}  # 하위 도메인
    assert names("지마켓과 에누리에서 최저가") == {"지마켓", "에누리"}  # 사이트 이름
    assert "다나와" in names("https://www.danawa.com 에서 검색")  # 작업 문장 속 주소
    assert names("다음 단계로 진행") == set()  # 흔한 단어('다음')는 이름으로 보지 않는다
    assert names("example.com 확인", "https://example.com") == set()
    assert site_tips.for_url("https://m.gmarket.co.kr/x").name == "지마켓" and site_tips.for_url("https://example.com") is None
    assert site_tips.for_url("not a url") is None


def test_tip_block_marks_screen_priority_only_for_just_in_time_hint():
    t = site_tips.for_url("https://www.danawa.com")
    assert "[사이트 요령 · 다나와 · 확인 2026-" in t.block() and "화면을 우선" in t.block()
    assert "화면을 우선" not in t.block(hint=False) and "sort=priceASC" in t.body


def test_just_in_time_tip_is_appended_once_per_site():
    tool = bt.BrowserActionTool(user_id="u1")
    out = "URL: https://search.danawa.com/x\nTitle: T"
    tool.last_url = "https://search.danawa.com/x"
    first = tool._with_site_tip(out)
    assert first.startswith(out) and "[사이트 요령 · 다나와" in first
    assert tool._with_site_tip(out) == out  # 두 번째 방문부터는 붙이지 않는다
    tool.last_url = "https://example.com/"
    assert tool._with_site_tip(out) == out  # 요령이 없는 사이트
    tool.last_url = "https://www.gmarket.co.kr/"
    assert "[사이트 요령 · 지마켓" in tool._with_site_tip(out)
    tool.last_url = "https://www.enuri.com/"
    assert tool._with_site_tip("Error: 이동 실패") == "Error: 이동 실패"  # 오류 결과에는 붙이지 않는다
    # 시작할 때 이미 지침에 넣은 사이트는 다시 붙이지 않는다
    pre = bt.BrowserActionTool(user_id="u1", tips_shown={"에누리"})
    pre.last_url = "https://www.enuri.com/"
    assert pre._with_site_tip(out) == out
    # 도구 인스턴스마다 안내 이력이 따로다 (병렬 실행끼리 공유하지 않는다)
    assert bt.BrowserActionTool(user_id="u2").tips_shown == set()


@pytest.mark.asyncio
async def test_start_instructions_include_only_matching_site_tips(monkeypatch):
    captured = {}

    class FakeAgent:
        def __init__(self, **kw):
            captured.update(kw)

        async def arun(self, prompt):
            class R:
                content = "완료"

            return R()

    import agno.agent as agno_agent

    monkeypatch.setattr(agno_agent, "Agent", FakeAgent)
    monkeypatch.setattr("app.agent.agno_engine.build_agno_model", lambda *a, **k: object())

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(bt, "persist_profile", noop)
    tool = bt.CliBrowserAgentTool(user_id="u1", login_enabled=False)
    out = await tool._arun_inner("다나와에서 진라면 검색", "https://www.danawa.com")
    assert "완료" in out
    ins = captured["instructions"]
    assert any("[사이트 요령 · 다나와" in i for i in ins) and not any("지마켓" in i and "[사이트 요령" in i for i in ins)
    assert not any("화면을 우선하세요.)" in i for i in ins)  # 시작 지침에는 '화면 우선' 꼬리말을 중복해서 붙이지 않는다
    assert ins[: len(bt.BROWSER_INSTRUCTIONS)] == bt.BROWSER_INSTRUCTIONS

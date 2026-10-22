from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.agent.orchestrator import _build_memory_context
from app.services.memory_service import effective_importance, rank_episodes, tokens

NOW = datetime(2026, 10, 20, 12, 0, 0)


def mem(key, value, mtype="semantic", importance=5, days_ago=0, detail=None, source="auto_extracted"):
    when = NOW - timedelta(days=days_ago)
    return SimpleNamespace(
        key=key, value=value, memory_type=mtype, importance=importance, occurred_at=when if mtype == "episodic" else None,
        created_at=when, detail=detail, source=source, category="general",
    )


def test_episodic_importance_decays_by_half_life():
    assert effective_importance(mem("a", "x", "episodic", 8, days_ago=0), NOW) == 8
    assert abs(effective_importance(mem("a", "x", "episodic", 8, days_ago=90), NOW) - 4) < 1e-6
    assert effective_importance(mem("a", "x", "semantic", 8, days_ago=900), NOW) == 8  # 사실은 감쇠하지 않는다


def test_rank_episodes_needs_keyword_overlap_and_prefers_recent():
    old = mem("n1_old", "쿼리 N+1 문제 해결", "episodic", 8, days_ago=300,
              detail={"situation": "목록 API 느림", "resolution": "selectinload", "outcome": ""})
    new = mem("n1_new", "쿼리 N+1 다시 해결", "episodic", 8, days_ago=5,
              detail={"situation": "주문 API 느림", "resolution": "selectinload", "outcome": ""})
    other = mem("css", "버튼 색상 수정", "episodic", 9, days_ago=1, detail={"situation": "CSS", "resolution": "토큰", "outcome": ""})
    got = rank_episodes([old, new, other], "목록 쿼리가 너무 느려요 N+1 인가요?", 3, NOW)
    assert [m.key for m in got] == ["n1_new", "n1_old"]
    assert rank_episodes([other], "결제 모듈 리팩터링", 3, NOW) == []


def test_korean_prefix_tokens_match_with_particles():
    assert tokens("리팩터링을") & tokens("리팩터링")


def test_prompt_sections_are_separated():
    ctx = _build_memory_context(
        {
            "semantic": [mem("job", "백엔드 개발자")],
            "procedural": [mem("style", "예제 코드를 먼저 보여 준 뒤 원리를 설명한다", "procedural")],
            "episodic": [mem("fix", "N+1 해결", "episodic", detail={"situation": "느림", "resolution": "selectinload", "outcome": "빨라짐"})],
        },
        {"current_task": "결제 모듈"},
    )
    assert "사실" in ctx and "반드시 따르세요" in ctx and "관련 과거 사례" in ctx and "단기 기억" in ctx
    assert "상황: 느림 / 해결: selectinload / 결과: 빨라짐" in ctx
    assert _build_memory_context({}, {}) == ""

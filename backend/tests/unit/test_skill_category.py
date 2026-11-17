"""스킬 카테고리 자동 분류 — 규칙, LLM 폴백, 직접 지정 고정."""
import pytest

from app.services import skill_category as sc
from app.services import skill_service as ss

CASES = {
    ("pdf", "Use this skill whenever the user wants to do anything with PDF files: extract text, merge, split"): "document",
    ("xlsx", "spreadsheet file is the primary input or output. open, read, edit .xlsx, .csv"): "document",
    ("webapp-testing", "Toolkit for interacting with and testing local web applications using Playwright"): "dev",
    ("deep-research", "researching a topic across multiple sources, comparing options, synthesizing into a report"): "research",
    ("skill-creator", "Create new skills, modify and improve existing skills, and measure skill performance"): "ai",
    ("weekly-report", "주간 업무 보고서를 작성하고 회의록을 정리합니다"): "business",
    ("data-cleaner", "CSV 데이터를 정리하고 통계 분석 후 차트로 시각화합니다"): "data",
}


@pytest.mark.parametrize("key,expected", list(CASES.items()))
def test_rules_classify_clear_cases(key, expected):
    cat, confident = sc.classify_by_rules(*key)
    assert cat == expected and confident


def test_no_keywords_is_etc_and_unconfident():
    assert sc.classify_by_rules("mystery", "Does something unusual") == ("etc", False)
    assert sc.classify_by_rules("", "") == ("etc", False)


def test_docker_does_not_trigger_document_category():
    cat, _ = sc.classify_by_rules("container-tool", "Build a docker image")
    assert cat != "document"


def test_parse_llm_answer():
    assert sc.parse_llm_answer("dev") == "dev"
    assert sc.parse_llm_answer('"Design".') == "design"
    assert sc.parse_llm_answer("카테고리는 data 입니다") == "data"
    assert sc.parse_llm_answer("something else") is None
    assert sc.parse_llm_answer("") is None


@pytest.mark.asyncio
async def test_classify_uses_llm_only_when_unconfident(monkeypatch):
    calls: list[str] = []

    async def fake(name, desc):
        calls.append(name)
        return "design"

    monkeypatch.setattr(sc, "_ask_llm", fake)
    assert await sc.classify("pdf", "Work with PDF files, extract text and merge") == "document"
    assert calls == []  # 확정이면 LLM 호출 없음
    assert await sc.classify("mystery", "Does something unusual") == "design"
    assert calls == ["mystery"]
    assert await sc.classify("mystery", "Does something unusual", use_llm=False) == "etc"


@pytest.mark.asyncio
async def test_classify_falls_back_to_rules_when_llm_fails(monkeypatch):
    async def boom(name, desc):
        raise RuntimeError("no llm")

    monkeypatch.setattr(sc, "_ask_llm", boom)
    # 규칙상 1위는 dev 이지만 확정이 아닌 설명 → LLM 실패 시 1위 규칙 결과
    assert await sc.classify("frontend-design", "Create distinctive production-grade frontend interfaces", True) in ("dev", "design")
    assert await sc.classify("mystery", "Does something unusual") == "etc"


class FakeSkill:
    def __init__(self, name, desc, category=None, locked=False):
        self.name, self.description, self.category, self.category_locked = name, desc, category, locked


class FakeDb:
    commits = 0

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_assign_categories_skips_locked_and_already_classified(monkeypatch):
    async def no_llm(name, desc):
        return None

    monkeypatch.setattr(sc, "_ask_llm", no_llm)
    new = FakeSkill("pdf", "Work with PDF files, extract text and merge")
    locked = FakeSkill("pdf2", "Work with PDF files", category="dev", locked=True)
    done = FakeSkill("pdf3", "Work with PDF files", category="dev")
    db = FakeDb()
    changed = await ss.assign_categories([new, locked, done], db)
    assert changed == 1 and new.category == "document"
    assert locked.category == "dev" and done.category == "dev"  # 직접 고른 것·이미 분류된 것은 유지
    # force: 고정되지 않은 것은 다시 분류, 고정된 것은 그대로
    await ss.assign_categories([new, locked, done], db, force=True)
    assert done.category == "document" and locked.category == "dev"


def test_every_category_has_label_and_prompt_lists_all():
    assert set(sc.LABELS) == set(sc.CATEGORY_IDS) and sc.ETC in sc.CATEGORY_IDS
    assert sc.CATEGORY_IDS[-1] == sc.ETC  # '기타' 는 항상 마지막

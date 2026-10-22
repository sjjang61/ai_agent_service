import re
from pathlib import Path

import pytest

from app.agent import prompts
from app.agent.agno_engine import AGENT_SPECS

APP = Path(__file__).resolve().parents[2] / "app"
PROMPT_DIR = APP / "agent" / "prompts"
_REF = re.compile(r"""\b(?:load|render|sections|agent_spec|team_prompt)\(\s*f?["']([a-z_{}\w]+)["']""")


def _referenced() -> set:
    names = set()
    for py in APP.rglob("*.py"):
        if py == PROMPT_DIR / "__init__.py":
            continue
        for n in _REF.findall(py.read_text(encoding="utf-8")):
            if "{" in n:  # subagent_{key} 같은 동적 이름은 실제 키로 펼친다
                names |= {n.replace("{key}", k) for k in AGENT_SPECS}
            else:
                names.add(n)
    return names


def test_every_prompt_file_is_used_and_every_reference_exists():
    files = {p.stem for p in PROMPT_DIR.glob("*.md") if p.stem != "README"}
    refs = _referenced() | {"system"}  # SYSTEM_PROMPT = load("system") 은 로더 모듈 안에 있다
    assert files - refs == set(), f"사용되지 않는 프롬프트 파일: {sorted(files - refs)}"
    assert refs - files == set(), f"파일이 없는 프롬프트 참조: {sorted(refs - files)}"


def test_render_requires_exact_placeholders():
    assert prompts.render("sub_agent_task", task="T", context="C") == "T\n\n[Context]\nC"
    with pytest.raises(KeyError):
        prompts.render("sub_agent_task", task="T")  # 값이 빠짐
    with pytest.raises(KeyError):
        prompts.render("sub_agent_task", task="T", context="C", extra="x")  # 파일에 없는 값


def test_placeholder_named_name_does_not_clash_with_the_prompt_name_argument():
    assert "리서처" in prompts.render("custom_agent", name="리서처", instructions="지침")


def test_json_braces_in_prompts_are_left_alone():
    text = prompts.render("memory_extraction", user_message="u", agent_response="a", existing="e", max_items=3)
    assert '[{"key": "..."' in text and "{{" not in text


def test_sections_and_agent_spec_split_on_separator_lines():
    role, instructions = prompts.agent_spec("subagent_coder")
    assert role.startswith("sandbox") and len(instructions) == 3
    assert len(prompts.sections("browser_agent")) == 6
    assert len(prompts.sections("team_default")) == 4


def test_system_prompt_is_loaded_from_markdown():
    assert prompts.SYSTEM_PROMPT.startswith("당신은 사용자의 복잡한 작업을 수행하는 AI 에이전트입니다.")

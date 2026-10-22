"""LLM 에 보내는 모든 프롬프트는 이 폴더의 .md 파일에서 관리한다.

- 프롬프트를 고치려면 해당 .md 파일만 수정하면 된다 (서버 재시작 필요 — 파일은 처음 읽을 때 캐시된다).
- 값이 들어갈 자리는 ``{{이름}}`` 으로 쓴다. JSON 예시의 ``{ }`` 는 그대로 써도 된다.
- 한 파일에 여러 문단을 목록으로 쓰는 프롬프트(팀 지침, 서브에이전트 등)는 ``---`` 만 있는 줄로 문단을 나눈다.
- 파일 앞뒤의 빈 줄은 무시된다. 섹션 사이의 간격은 코드가 붙인다.

파일 목록과 사용처는 README.md 를 참고한다.
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

_DIR = Path(__file__).parent
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_SEPARATOR = re.compile(r"^---[ \t]*$", re.MULTILINE)


@lru_cache(maxsize=None)
def load(name: str) -> str:
    """프롬프트 원문 (앞뒤 빈 줄 제거)."""
    return (_DIR / f"{name}.md").read_text(encoding="utf-8").strip("\n")


def render(name: str, /, **values) -> str:  # name 은 위치 전용: 프롬프트 안의 {{name}} 자리와 충돌하지 않게 한다
    """``{{이름}}`` 자리에 값을 채운다. 파일에 없는 이름을 넘기거나 값 없이 남는 자리가 있으면 예외 (오타 방지)."""
    text = load(name)
    wanted = set(_PLACEHOLDER.findall(text))
    given = set(values)
    if wanted != given:
        raise KeyError(f"prompt '{name}': placeholders {sorted(wanted)} != values {sorted(given)}")
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text)


def sections(name: str) -> List[str]:
    """``---`` 줄로 나뉜 문단 목록."""
    return [p.strip() for p in _SEPARATOR.split(load(name)) if p.strip()]


def agent_spec(name: str) -> Tuple[str, List[str]]:
    """서브에이전트 정의 파일: 첫 문단은 역할(role), 나머지는 지침(instructions)."""
    parts = sections(name)
    return parts[0], parts[1:]


SYSTEM_PROMPT: str = load("system")

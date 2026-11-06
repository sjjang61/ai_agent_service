import asyncio
from unittest.mock import patch

from app.services import skill_translate as st


def test_split_keeps_code_blocks_whole():
    code = "```python\n" + "\n\n".join(f"x{i} = {i}" for i in range(200)) + "\n```"
    text = "# 제목\n\n본문 하나\n\n" + code + "\n\n끝 문단\n"
    chunks = st.split_chunks(text, limit=300)
    assert len(chunks) >= 2
    assert sum(c.count("```") for c in chunks) == 2 and any(c.count("```") == 2 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks) == text.replace("\n", "")


def test_clean_output_strips_wrapping_fence():
    assert st.clean_output("```markdown\n# 안녕\n본문\n```") == "# 안녕\n본문"
    assert st.clean_output("# 안녕") == "# 안녕"
    assert st.clean_output("```python\nprint(1)\n```\n설명") == "```python\nprint(1)\n```\n설명"


def test_translate_truncates_and_calls_llm():
    calls = []

    class FakeLLM:
        async def ainvoke(self, prompt):
            calls.append(prompt)
            return type("R", (), {"content": "번역됨"})()

    class FakeRunner:
        def __init__(self, tools):
            self.llm = FakeLLM()

    with patch("app.agent.react_agent.AgentRunner", FakeRunner):
        r = asyncio.run(st.translate_to_korean("hello\n\nworld\n"))
        assert r == {"content": "번역됨", "truncated": False} and "hello" in calls[0]
        big = asyncio.run(st.translate_to_korean("가나다 abc\n\n" * 6000))
        assert big["truncated"] is True


def test_content_hash_changes_with_content():
    assert st.content_hash("a") == st.content_hash("a") != st.content_hash("b")

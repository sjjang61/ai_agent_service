from app.services.followup_service import parse_questions


def test_parse_questions_normalizes():
    assert parse_questions('{"questions": ["첫째  질문", "둘째 질문", "셋째"]}') == ["첫째 질문", "둘째 질문"]
    assert parse_questions('설명\n```json\n{"questions": ["a?", "a?", "b?"]}\n```') == ["a?", "b?"]


def test_parse_questions_rejects_bad_input():
    assert parse_questions("") == []
    assert parse_questions("not json") == []
    assert parse_questions('{"questions": "x"}') == []
    assert parse_questions('{"questions": ["", "  ", "' + "가" * 200 + '"]}') == []
    assert parse_questions('{"questions": []}') == []

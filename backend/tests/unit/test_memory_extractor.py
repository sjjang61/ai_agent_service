from app.services.memory_extractor import MAX_ITEMS_PER_TURN, parse_items


def test_parses_scope_and_normalizes_key():
    items = parse_items(
        '설명 [{"key": "Preferred Language", "value": "한국어로 답변", "type": "procedural", "category": "preference", "importance": 9},'
        ' {"key": "current_goal", "value": "이번 주 보고서 작성", "type": "short"}] 끝'
    )
    assert [(i["key"], i["type"], i["importance"]) for i in items] == [
        ("preferred_language", "procedural", 9),
        ("current_goal", "short", 5),
    ]
    assert items[0]["category"] == "instruction"  # procedural 은 항상 instruction
    assert items[1]["category"] == "general"


def test_drops_secrets_and_invalid_items():
    items = parse_items(
        '[{"key": "api", "value": "내 키는 sk-abcdefghijklmnopqrstuvwx"}, {"key": "pw", "value": "password: hunter2"},'
        ' {"key": "", "value": "x"}, "text", {"key": "ok", "value": "서울 거주"}]'
    )
    assert [i["key"] for i in items] == ["ok"]


def test_empty_and_garbage():
    assert parse_items("[]") == []
    assert parse_items("없음") == []
    assert parse_items("[not json]") == []


def test_caps_items_per_turn():
    body = ",".join(f'{{"key": "k{i}", "value": "v{i}"}}' for i in range(20))
    assert len(parse_items(f"[{body}]")) == MAX_ITEMS_PER_TURN


def test_legacy_scope_format_and_unknown_type():
    items = parse_items(
        '[{"key": "a", "value": "x", "scope": "long", "category": "instruction"},'
        ' {"key": "b", "value": "y", "scope": "short"}, {"key": "c", "value": "z", "type": "weird"}]'
    )
    assert [(i["key"], i["type"]) for i in items] == [("a", "procedural"), ("b", "short"), ("c", "semantic")]


def test_episodic_requires_situation_and_resolution():
    items = parse_items(
        '[{"key": "n1_fix", "value": "N+1 쿼리 해결", "type": "episodic", "importance": 7,'
        ' "situation": "목록 API 가 느림", "resolution": "selectinload 적용", "outcome": "응답 8초→0.4초"},'
        ' {"key": "bad", "value": "해결 안 됨", "type": "episodic", "situation": "문제만 있음"}]'
    )
    assert [i["key"] for i in items] == ["n1_fix"]
    assert items[0]["detail"] == {"situation": "목록 API 가 느림", "resolution": "selectinload 적용", "outcome": "응답 8초→0.4초"}
    assert items[0]["category"] == "general"

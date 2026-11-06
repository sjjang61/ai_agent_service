from app.services import short_memory_merge as sm


def test_parse_groups_repairs_llm_output():
    # 범위를 벗어난 번호·중복은 버리고, 빠진 항목은 항목 1개짜리 그룹으로 채운다
    text = '```json\n{"groups": [{"title": "  일본   여행 ", "items": [0, 2, 2, 9, "x"]}, {"title": "", "items": [2]}]}\n```'
    g = sm.parse_groups(text, 4)
    assert g[0] == {"title": "일본 여행", "indices": [0, 2]}
    assert [x["indices"] for x in g[1:]] == [[1], [3]]
    assert sorted(i for x in g for i in x["indices"]) == [0, 1, 2, 3]            # 모든 항목이 정확히 한 번씩
    assert sm.parse_groups("not json", 2) == [{"title": "", "indices": [0]}, {"title": "", "indices": [1]}]


def test_parse_merged_normalizes_and_caps():
    text = '{"items": [{"key": "Trip Schedule!", "value": "  12/3~12/9  여행 "}, {"key": "trip_schedule", "value": "중복"}, {"key": "", "value": "x"}, {"key": "k", "value": ""}, {"key": "ok", "value": "v"}]}'
    assert sm.parse_merged(text) == [{"key": "trip_schedule", "value": "12/3~12/9 여행"}, {"key": "ok", "value": "v"}]
    many = '{"items": [' + ",".join(f'{{"key":"k{i}","value":"v"}}' for i in range(20)) + "]}"
    assert len(sm.parse_merged(many)) == sm.MAX_MERGED
    assert sm.parse_merged("") == []


def test_unique_key_adds_a_suffix_on_collision():
    assert sm.unique_key("a", set()) == "a" and sm.unique_key("a", {"a"}) == "a_2" and sm.unique_key("a", {"a", "a_2"}) == "a_3"

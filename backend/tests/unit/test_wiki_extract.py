from app.services.wiki_extract import content_hash, norm, parse_extraction


def test_parse_extraction_validates():
    txt = '''{"entities":[
      {"name":"피치항공","type":"entity","aliases":["Peach","peach"],"summary":"저가 항공사"},
      {"name":"간사이 공항","type":"entity","aliases":[],"summary":""},
      {"name":"피치 항공","type":"entity"},
      {"name":"","type":"concept"},
      {"name":"비용 절감","type":"concept","summary":"x"}],
     "relations":[
      {"source":"피치항공","target":"간사이 공항","label":"취항한다"},
      {"source":"Peach","target":"비용 절감","label":"추구한다"},
      {"source":"피치항공","target":"없는것","label":"x"},
      {"source":"피치항공","target":"피치항공","label":"x"}]}'''
    ents, rels = parse_extraction(txt)
    assert [e["name"] for e in ents] == ["피치항공", "간사이 공항", "비용 절감"]
    assert ents[0]["aliases"] == ["Peach"]  # 이름과 같은 표기(peach 중복)는 제외
    assert ents[2]["type"] == "concept"
    assert rels == [{"source": "피치항공", "target": "간사이 공항", "label": "취항한다"}, {"source": "피치항공", "target": "비용 절감", "label": "추구한다"}]


def test_parse_garbage_and_norm():
    assert parse_extraction("없음") == ([], [])
    assert norm("Wiki-Index (v2)") == "wikiindexv2"
    assert content_hash("a", "b") != content_hash("a", "c")

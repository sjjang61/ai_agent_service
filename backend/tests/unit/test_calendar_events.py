from app.services.calendar_events import parse_events

ITEMS = [{"conversation_id": "c1", "conversation_title": "여행", "key": "trip", "value": "x"}]


def test_parse_events_validates():
    txt = '''{"events":[
      {"title":"오사카 여행","start_date":"2026-12-03","end_date":"2026-12-09","start_time":"11:00","end_time":"25:00","note":"성인2 아동2","source":0},
      {"title":"잘못","start_date":"nope"},
      {"title":"역전","start_date":"2026-12-05","end_date":"2026-12-01","source":9}]}'''
    ev = parse_events(txt, ITEMS)
    assert [e["title"] for e in ev] == ["오사카 여행", "역전"]
    assert ev[0]["end_time"] == "" and ev[0]["start_time"] == "11:00" and ev[0]["conversation_id"] == "c1"
    assert ev[1]["end_date"] == "2026-12-05" and ev[1]["conversation_id"] is None


def test_parse_events_garbage():
    assert parse_events("없음", ITEMS) == []


def test_memory_items_filters():
    from datetime import datetime
    from types import SimpleNamespace as N
    from app.services.calendar_events import memory_items, parse_events

    mk = lambda **k: N(**{"key": "k", "value": "v", "memory_type": "semantic", "expires_at": None, "id": "m1", **k})
    ms = [
        mk(key="trip", value="12월 3일 출국", expires_at=datetime(2026, 12, 9, 15, 0)),  # KST 12/10 00:00 → 종료일 12/9
        mk(key="likes", value="커피를 좋아한다"),                                           # 날짜 없음 → 제외
        mk(key="calendar_ab", value="치과 (2026-12-20)", expires_at=datetime(2026, 12, 20, 15)),  # 캘린더 연동 → 제외
        mk(key="how", value="항상 2026년 형식", memory_type="procedural"),                    # 절차 → 제외
        mk(key="exam", value="시험은 2027-01-15"),                                           # 본문 날짜 → 포함
    ]
    items = memory_items(ms)
    assert [i["key"] for i in items] == ["trip", "exam"]
    assert items[0]["valid_until"] == "2026-12-09" and items[1]["valid_until"] is None
    ev = parse_events('{"events":[{"title":"출국","start_date":"2026-12-03","end_date":"2026-12-09","source":0}]}', items)
    assert ev[0]["source_kind"] == "memory" and ev[0]["memory_id"] == "m1" and ev[0]["conversation_id"] is None

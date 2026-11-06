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

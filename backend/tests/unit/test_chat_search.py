from app.services.chat_search import like_pattern, make_snippet


def test_like_pattern_escapes_wildcards():
    assert like_pattern("100%_a") == "%100\\%\\_a%"
    assert like_pattern("a\\b") == "%a\\\\b%"


def test_snippet_centers_on_match_and_marks_cuts():
    text = "가" * 100 + "오목 게임" + "나" * 100
    s = make_snippet(text, "오목")
    assert "오목 게임" in s and s.startswith("…") and s.endswith("…") and len(s) < 120
    assert make_snippet("짧은 오목 문장", "오목") == "짧은 오목 문장"          # 잘리지 않으면 …없음
    assert make_snippet("Hello World", "WORLD") == "Hello World"            # 대소문자 무시
    assert make_snippet("a\n\n  b   c", "b") == "a b c"                       # 공백 정리
    assert make_snippet("abc", "zzz") == "abc"

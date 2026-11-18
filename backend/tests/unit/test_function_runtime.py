"""Function 실행기: 로그 파서(결과 마커 분리·한도), 마스킹, 이미지 선택 (Docker 없이)"""
from app.services.function_runtime import _LogParser, _mask, image_for, make_tar
import tarfile, io

TOKEN = "abc123"
MARK = f"__FN_RESULT_{TOKEN}__ "


def parse(chunks, log_cap=1000, result_cap=1000):
    p = _LogParser(TOKEN, log_cap, result_cap)
    for c in chunks:
        p.feed(c)
    p.finish()
    return p


def test_separates_result_from_logs_even_when_split_across_chunks():
    data = ("hello\nworld\n\n" + MARK + '{"ok": true, "result": 1}\n').encode()
    for size in (1, 3, 7, 64, len(data)):
        p = parse([data[i:i + size] for i in range(0, len(data), size)])
        assert p.result_line == b'{"ok": true, "result": 1}', size
        assert p.log.decode() == "hello\nworld\n\n", size
        assert not p.truncated and not p.result_too_large


def test_forged_marker_with_other_token_is_just_a_log_line():
    p = parse([b'__FN_RESULT_other__ {"ok": true, "result": "forged"}\n', (MARK + '{"ok": true, "result": "real"}\n').encode()])
    assert p.result_line == b'{"ok": true, "result": "real"}'
    assert b"forged" in p.log


def test_marker_line_without_trailing_newline_is_still_found():
    p = parse([b"partial output", ("\n" + MARK + '{"ok": true}').encode()])
    assert p.result_line == b'{"ok": true}' and bytes(p.log) == b"partial output\n"


def test_log_is_capped_but_result_survives_a_flood():
    flood = [b"x" * 100 + b"\n"] * 5000
    p = parse(flood + [(MARK + '{"ok": true, "result": "done"}\n').encode()], log_cap=1000)
    assert p.truncated and len(p.log) <= 1000 and p.result_line == b'{"ok": true, "result": "done"}'


def test_oversized_result_line_is_flagged_not_truncated_into_garbage():
    huge = (MARK + '{"ok": true, "result": "' + "x" * 5000 + '"}\n').encode()
    for size in (50, 999, len(huge)):
        p = parse([huge[i:i + size] for i in range(0, len(huge), size)], result_cap=1000)
        assert p.result_too_large and p.result_line is None, size


def test_huge_line_without_newline_does_not_grow_memory_and_later_lines_work():
    p = _LogParser(TOKEN, 100, 100)
    for _ in range(200):
        p.feed(b"y" * 100)  # 줄바꿈 없는 2만 바이트
    assert len(p._partial) < 1000  # 한도를 넘으면 버린다
    p.feed(b"\nnext line\n" + (MARK + '{"ok": true}\n').encode())
    p.finish()
    # 긴 줄이 로그 한도를 채웠으므로 이후 로그는 버려지지만(truncated), 줄 경계는 복구되어 결과 마커는 정상으로 읽힌다
    assert p.truncated and p.result_line == b'{"ok": true}'


def test_mask_replaces_all_secret_values_longest_first_and_ignores_tiny_values():
    assert _mask("k=abcdef and abc", ["abc", "abcdef"]) == "k=*** and ***"
    assert _mask("a b c", ["a", ""]) == "a b c"  # 1~2자 값은 가리지 않는다(로그가 망가진다)


def test_image_for_runtime():
    assert image_for("python3.12").endswith("fn-python:latest") and image_for("bun").endswith("fn-bun:latest")


def test_make_tar_sets_owner_and_modes():
    t = tarfile.open(fileobj=io.BytesIO(make_tar({"a.txt": b"1", "run.sh": (b"#!/bin/sh\n", 0o755)})))
    m = {x.name: x for x in t}
    assert m["a.txt"].uid == 1000 and m["a.txt"].mode == 0o644 and m["run.sh"].mode == 0o755

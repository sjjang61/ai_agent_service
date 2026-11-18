"""Function 패키지 검증: 악성 zip 샘플은 전부 거부하고, 정상 zip 은 안전한 tar.gz 로 정규화한다"""
import gzip
import io
import json
import struct
import tarfile
import zipfile

import pytest

from app.config import settings
from app.services.function_package import PackageError, build_zip, inspect_zip, normalize_config

CFG = {"runtime": "python3.12", "handler": "main.handler"}
OK_FILES = {"function.json": json.dumps(CFG), "main.py": "def handler(e, c):\n    return 1\n"}


def zipped(entries):
    """entries: {이름: bytes|str|(bytes, external_attr)} → zip (ZipInfo 로 직접 만들어 심볼릭 링크 등도 흉내 낸다)"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, val in entries.items():
            data, attr = val if isinstance(val, tuple) else (val, None)
            zi = zipfile.ZipInfo(name)
            if attr is not None:
                zi.external_attr = attr << 16
            z.writestr(zi, data)
    return buf.getvalue()


def tar_of(info):
    return tarfile.open(fileobj=io.BytesIO(gzip.decompress(info.tar_gz)))


def test_valid_package_is_normalized_into_a_safe_tar():
    info = inspect_zip(build_zip({**OK_FILES, "lib/util.py": "X = 1\n", "lib/__init__.py": ""}))
    assert info.config == {"runtime": "python3.12", "handler": "main.handler", "timeout_seconds": settings.FUNCTION_TIMEOUT_DEFAULT,
                           "memory_mb": settings.FUNCTION_MEMORY_DEFAULT_MB, "allow_network": False, "env": {}}
    t = tar_of(info)
    names = {m.name: m for m in t}
    assert {"function.json", "main.py", "lib", "lib/util.py"} <= set(names)
    assert names["lib"].isdir() and all(m.uid == 1000 and m.gid == 1000 for m in names.values())
    assert info.file_count == 4 and info.tar_bytes == len(gzip.decompress(info.tar_gz)) and len(info.sha256) == 64


def test_same_zip_has_same_hash_and_executable_bit_is_kept():
    z = zipped({**{k: v for k, v in OK_FILES.items()}, "run.sh": (b"#!/bin/sh\n", 0o100755), "data.txt": (b"x", 0o100644)})
    a, b = inspect_zip(z), inspect_zip(z)
    assert a.sha256 == b.sha256
    m = {x.name: x for x in tar_of(a)}
    assert m["run.sh"].mode == 0o755 and m["data.txt"].mode == 0o644


def test_single_top_level_folder_is_stripped_and_junk_ignored():
    z = build_zip({f"proj/{k}": v for k, v in OK_FILES.items()} | {"__MACOSX/proj/._main.py": "junk", "proj/.DS_Store": "junk"})
    names = {m.name for m in tar_of(inspect_zip(z))}
    assert names == {"function.json", "main.py"}


@pytest.mark.parametrize("bad", ["../evil.py", "a/../../evil.py", "/etc/passwd", "C:\\win\\x.py", "..\\evil.py", "ok/../../x"])
def test_path_escape_is_rejected(bad):
    with pytest.raises(PackageError, match="허용되지 않는 경로"):
        inspect_zip(zipped({**OK_FILES, bad: "x"}))


def test_symlink_and_device_entries_are_rejected():
    with pytest.raises(PackageError, match="심볼릭 링크"):
        inspect_zip(zipped({**OK_FILES, "link": (b"/etc/passwd", 0o120777)}))
    with pytest.raises(PackageError, match="일반 파일이 아닌"):
        inspect_zip(zipped({**OK_FILES, "dev": (b"", 0o020666)}))


def test_encrypted_zip_is_rejected():
    z = bytearray(zipped(OK_FILES))
    # 첫 로컬 헤더(오프셋 6)와 중앙 디렉터리의 일반 목적 비트 플래그에 암호화 비트를 켠다
    z[6] |= 1
    i = z.find(b"PK\x01\x02")
    z[i + 8] |= 1
    with pytest.raises(PackageError, match="암호"):
        inspect_zip(bytes(z))


def test_not_a_zip_and_oversize():
    with pytest.raises(PackageError, match="zip"):
        inspect_zip(b"not a zip at all")
    with pytest.raises(PackageError, match="MB"):
        inspect_zip(b"x" * (settings.FUNCTION_PACKAGE_MAX_MB * 1024 * 1024 + 1))


def test_zip_bomb_by_declared_and_by_actual_size(monkeypatch):
    monkeypatch.setattr(settings, "FUNCTION_UNPACKED_MAX_MB", 1)
    bomb = build_zip({**OK_FILES, "big.bin": b"\x00" * (3 * 1024 * 1024)})  # 3MB 가 수 KB 로 압축된다
    assert len(bomb) < 20000
    with pytest.raises(PackageError, match="넘"):
        inspect_zip(bomb)


def test_lying_header_size_is_rejected(monkeypatch):
    """헤더의 file_size 를 작게 속이고 실제로는 큰 데이터를 넣은 zip (선언 크기 검사만 하면 통과한다)"""
    z = bytearray(zipped({**OK_FILES, "payload.bin": b"A" * 5000}))
    i = z.find(b"PK\x01\x02payload".replace(b"payload", b""))  # 첫 중앙 디렉터리 항목부터 payload 항목을 찾는다
    while i >= 0:
        name_len = struct.unpack("<H", z[i + 28:i + 30])[0]
        if bytes(z[i + 46:i + 46 + name_len]) == b"payload.bin":
            struct.pack_into("<I", z, i + 24, 10)  # 중앙 디렉터리의 비압축 크기를 10 으로 속인다
            break
        i = z.find(b"PK\x01\x02", i + 4)
    with pytest.raises(PackageError):
        inspect_zip(bytes(z))


def test_too_many_files(monkeypatch):
    monkeypatch.setattr(settings, "FUNCTION_PACKAGE_MAX_FILES", 3)
    with pytest.raises(PackageError, match="파일이 너무 많습니다"):
        inspect_zip(build_zip({**OK_FILES, "a": "1", "b": "2"}))


def test_function_json_required_and_validated():
    with pytest.raises(PackageError, match="function.json"):
        inspect_zip(build_zip({"main.py": "x"}))
    with pytest.raises(PackageError, match="읽을 수 없습니다"):
        inspect_zip(build_zip({"function.json": "{not json", "main.py": "x"}))
    with pytest.raises(PackageError, match="핸들러 파일"):
        inspect_zip(build_zip({"function.json": json.dumps(CFG)}))  # main.py 없음
    with pytest.raises(PackageError, match="두 번"):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("function.json", json.dumps(CFG)); z.writestr("main.py", "x"); z.writestr("main.py", "y")
        inspect_zip(buf.getvalue())


@pytest.mark.parametrize("patch,msg", [
    ({"runtime": "ruby"}, "runtime"),
    ({"handler": "nofunction"}, "handler"),
    ({"handler": "../x.handler"}, "handler"),
    ({"timeout_seconds": 0}, "timeout_seconds"),
    ({"timeout_seconds": 100000}, "timeout_seconds"),
    ({"timeout_seconds": True}, "timeout_seconds"),
    ({"memory_mb": 8}, "memory_mb"),
    ({"memory_mb": 10**6}, "memory_mb"),
    ({"allow_network": "yes"}, "allow_network"),
    ({"env": {"FN_TOKEN": "x"}}, "환경변수"),
    ({"env": {"PATH": "/x"}}, "환경변수"),
    ({"env": {"1BAD": "x"}}, "환경변수"),
    ({"env": {"OK": 5}}, "환경변수"),
    ({"env": {f"K{i}": "v" for i in range(51)}}, "50개"),
])
def test_config_validation(patch, msg):
    with pytest.raises(PackageError, match=msg):
        normalize_config({**CFG, **patch})


def test_bun_handler_resolution_and_python_package_handler():
    ok = inspect_zip(build_zip({"function.json": json.dumps({"runtime": "bun", "handler": "index.handler"}), "index.ts": "export const handler = () => 1"}))
    assert ok.config["runtime"] == "bun"
    with pytest.raises(PackageError, match="핸들러 파일"):
        inspect_zip(build_zip({"function.json": json.dumps({"runtime": "bun", "handler": "index.handler"}), "index.py": "x"}))
    pkg = inspect_zip(build_zip({"function.json": json.dumps({"runtime": "python3.12", "handler": "app.main.handler"}), "app/main.py": "x"}))
    assert pkg.config["handler"] == "app.main.handler"

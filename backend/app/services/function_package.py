"""Function 패키지(zip) 검증·정규화.

사용자가 올린 zip 은 신뢰하지 않는다. 항목을 하나씩 검증해 **새 tar.gz 로 다시 만들고**, 컨테이너는 이 tar 만 푼다
(그래서 컨테이너 안으로 안전하지 않은 경로·링크·장치 파일이 들어갈 수 없다).

거부: 암호가 걸린 zip, 절대 경로·'..'·NUL, 심볼릭 링크·장치 파일, 파일 수·크기 한도 초과, 실제로 풀었을 때 헤더와 다른 크기(압축 폭탄),
function.json 이 없거나 잘못된 경우, 핸들러 파일이 없는 경우.
"""
import gzip
import hashlib
import io
import json
import posixpath
import re
import stat
import tarfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.config import settings

_MB = 1024 * 1024
RUNTIMES = ("python3.12", "bun")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
RESERVED_ENV = {"PATH", "HOME", "USER", "PWD", "SHELL", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME", "NODE_OPTIONS", "BUN_INSTALL"}
HANDLER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z_][A-Za-z0-9_]*$")
_JUNK = ("__MACOSX", ".DS_Store")
BUN_EXT = ("ts", "js", "mjs", "cjs")


class PackageError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 패키지 오류 문구"""


@dataclass
class PackageInfo:
    config: dict
    sha256: str  # 원본 zip 의 해시
    tar_gz: bytes  # 검증·정규화한 실행용 아카이브
    tar_bytes: int  # 압축을 푼 tar 길이
    unpacked_bytes: int
    file_count: int


def normalize_config(raw: dict) -> dict:
    """function.json 검증 + 기본값 채우기. 잘못되면 PackageError."""
    if not isinstance(raw, dict):
        raise PackageError("function.json 은 JSON 객체여야 합니다")
    runtime = raw.get("runtime")
    if runtime not in RUNTIMES:
        raise PackageError(f"runtime 은 {' | '.join(RUNTIMES)} 중 하나여야 합니다 (현재: {runtime!r})")
    handler = raw.get("handler")
    if not isinstance(handler, str) or not HANDLER_RE.match(handler) or ".." in handler:
        raise PackageError("handler 는 '파일.함수' 형식이어야 합니다 (예: main.handler)")
    timeout = raw.get("timeout_seconds", settings.FUNCTION_TIMEOUT_DEFAULT)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= settings.FUNCTION_TIMEOUT_MAX:
        raise PackageError(f"timeout_seconds 는 1~{settings.FUNCTION_TIMEOUT_MAX} 사이의 정수여야 합니다")
    memory = raw.get("memory_mb", settings.FUNCTION_MEMORY_DEFAULT_MB)
    if not isinstance(memory, int) or isinstance(memory, bool) or not 64 <= memory <= settings.FUNCTION_MEMORY_MAX_MB:
        raise PackageError(f"memory_mb 는 64~{settings.FUNCTION_MEMORY_MAX_MB} 사이의 정수여야 합니다")
    net = raw.get("allow_network", False)
    if not isinstance(net, bool):
        raise PackageError("allow_network 는 true/false 여야 합니다")
    env = raw.get("env", {})
    if not isinstance(env, dict) or len(env) > 50:
        raise PackageError("env 는 최대 50개의 {이름: 값} 객체여야 합니다")
    for k, v in env.items():
        if not ENV_NAME_RE.match(str(k)) or str(k).startswith("FN_") or str(k) in RESERVED_ENV:
            raise PackageError(f"사용할 수 없는 환경변수 이름입니다: {k} (FN_ 로 시작하거나 예약된 이름은 쓸 수 없습니다)")
        if not isinstance(v, str) or len(v) > 4096:
            raise PackageError(f"환경변수 {k} 의 값은 4096자 이하 문자열이어야 합니다 (비밀값은 시크릿으로 등록하세요)")
    return {"runtime": runtime, "handler": handler, "timeout_seconds": timeout, "memory_mb": memory, "allow_network": net, "env": dict(env)}


def _clean_name(name: str) -> str:
    n = name.replace("\\", "/")
    if "\x00" in n or n.startswith("/") or re.match(r"^[A-Za-z]:", n):
        raise PackageError(f"허용되지 않는 경로입니다: {name!r}")
    parts = [p for p in PurePosixPath(n).parts if p not in ("", ".")]
    if ".." in parts or not parts:
        raise PackageError(f"허용되지 않는 경로입니다: {name!r}")
    return "/".join(parts)


def _handler_exists(config: dict, files: set) -> bool:
    mod = config["handler"].rpartition(".")[0]
    if config["runtime"] == "python3.12":
        base = mod.replace(".", "/")
        return f"{base}.py" in files or f"{base}/__init__.py" in files
    return any(f"{mod}.{e}" in files for e in BUN_EXT)


def inspect_zip(data: bytes) -> PackageInfo:
    """zip 바이트를 검증하고 실행용 tar.gz 로 정규화한다."""
    if len(data) > settings.FUNCTION_PACKAGE_MAX_MB * _MB:
        raise PackageError(f"패키지는 {settings.FUNCTION_PACKAGE_MAX_MB}MB 까지 올릴 수 있습니다")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PackageError("zip 파일이 아니거나 손상되었습니다")
    infos = [i for i in zf.infolist() if not any(p in _JUNK for p in PurePosixPath(i.filename.replace("\\", "/")).parts)]
    if len(infos) > settings.FUNCTION_PACKAGE_MAX_FILES:
        raise PackageError(f"파일이 너무 많습니다 (최대 {settings.FUNCTION_PACKAGE_MAX_FILES}개)")
    limit = settings.FUNCTION_UNPACKED_MAX_MB * _MB
    declared = sum(i.file_size for i in infos)
    if declared > limit:
        raise PackageError(f"압축을 풀면 {settings.FUNCTION_UNPACKED_MAX_MB}MB 를 넘습니다")

    names = [_clean_name(i.filename) for i in infos]
    # 최상위 폴더 하나로 감싼 zip(zip -r dir) 은 그 폴더를 벗긴다
    strip = ""
    if "function.json" not in names:
        tops = {n.split("/")[0] for n in names}
        if len(tops) == 1 and f"{next(iter(tops))}/function.json" in names:
            strip = next(iter(tops)) + "/"
        else:
            raise PackageError("function.json 이 zip 의 최상위에 있어야 합니다")

    entries, total, seen = [], 0, set()
    for info, name in zip(infos, names):
        if info.flag_bits & 0x1:
            raise PackageError("암호가 걸린 zip 은 사용할 수 없습니다")
        rel = name[len(strip):] if name.startswith(strip) else None
        if rel is None or not rel:
            continue
        mode = (info.external_attr >> 16) & 0xFFFF
        ftype = stat.S_IFMT(mode)  # 파이썬 writestr·Windows 가 만든 zip 은 유형 비트가 0 이다: 그때는 일반 파일로 본다
        if ftype == stat.S_IFLNK:
            raise PackageError(f"심볼릭 링크는 포함할 수 없습니다: {rel}")
        if ftype and ftype not in (stat.S_IFREG, stat.S_IFDIR):
            raise PackageError(f"일반 파일이 아닌 항목은 포함할 수 없습니다: {rel}")
        if info.is_dir() or rel.endswith("/"):
            continue
        if rel in seen:
            raise PackageError(f"같은 경로가 두 번 들어 있습니다: {rel}")
        seen.add(rel)
        try:
            with zf.open(info) as f:  # 헤더 값을 믿지 않고 실제로 읽은 크기로 센다 (압축 폭탄 방지)
                body = f.read(limit - total + 1)
        except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, OSError) as e:
            raise PackageError(f"zip 항목을 읽을 수 없습니다 (손상되었거나 지원하지 않는 형식): {rel} ({type(e).__name__})")
        total += len(body)
        if total > limit or len(body) != info.file_size:
            raise PackageError(f"압축을 풀면 {settings.FUNCTION_UNPACKED_MAX_MB}MB 를 넘거나 zip 헤더의 크기와 다릅니다: {rel}")
        entries.append((rel, body, 0o755 if mode & 0o111 else 0o644))

    by_name = {r: b for r, b, _ in entries}
    try:
        config = normalize_config(json.loads(by_name["function.json"].decode("utf-8")))
    except (UnicodeDecodeError, ValueError) as e:
        raise PackageError(f"function.json 을 읽을 수 없습니다: {e}")
    if not _handler_exists(config, set(by_name)):
        raise PackageError(f"핸들러 파일을 찾을 수 없습니다: {config['handler']} ({config['runtime']})")

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as t:
        made_dirs: set = set()
        for rel, body, mode in sorted(entries):
            parent = posixpath.dirname(rel)
            chain = []
            while parent and parent not in made_dirs:
                chain.append(parent)
                parent = posixpath.dirname(parent)
            for d in reversed(chain):
                ti = tarfile.TarInfo(d)
                ti.type, ti.mode, ti.uid, ti.gid = tarfile.DIRTYPE, 0o755, 1000, 1000
                t.addfile(ti)
                made_dirs.add(d)
            ti = tarfile.TarInfo(rel)
            ti.size, ti.mode, ti.uid, ti.gid = len(body), mode, 1000, 1000
            t.addfile(ti, io.BytesIO(body))
    tar = raw.getvalue()
    return PackageInfo(config=config, sha256=hashlib.sha256(data).hexdigest(), tar_gz=gzip.compress(tar, 6), tar_bytes=len(tar), unpacked_bytes=total, file_count=len(entries))


def build_zip(files: dict) -> bytes:
    """{경로: bytes} → zip (에이전트 등록·테스트용)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def zip_from_tar(tar_path: str, max_bytes: int) -> tuple:
    """docker get_archive 가 준 tar(폴더 하나)를 zip 으로 바꾼다. 최상위 폴더 이름은 벗기고, 파일만 담는다(링크·장치·빈 폴더는 건너뜀).
    반환: (zip 바이트, 건너뛴 항목 수). 총 크기가 max_bytes 를 넘으면 PackageError."""
    buf = io.BytesIO()
    total = skipped = 0
    with tarfile.open(tar_path) as t, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for m in t:
            parts = [p for p in PurePosixPath(m.name).parts if p not in ("", ".")]
            if m.isdir():
                continue
            if not m.isfile() or ".." in parts or m.name.startswith("/") or len(parts) < 1:
                skipped += 1
                continue
            rel = "/".join(parts[1:]) if len(parts) > 1 else parts[0]
            if not rel or any(p in _JUNK for p in parts):
                continue
            total += m.size
            if total > max_bytes:
                raise PackageError(f"폴더가 너무 큽니다 (압축을 풀면 {max_bytes // _MB}MB 초과)")
            zi = zipfile.ZipInfo(rel)
            zi.external_attr = ((stat.S_IFREG | (0o755 if m.mode & 0o111 else 0o644)) & 0xFFFF) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, t.extractfile(m).read())
    return buf.getvalue(), skipped

"""데스크톱 로컬 브라우저의 작업 스크린샷 저장소.

로컬 브라우저는 사용자의 sandbox 없이 동작하므로(sandbox 가 꺼져 있는 경우가 많다), 스크린샷을 서버의 로컬 디스크에 사용자별로 보관한다.
sandbox 브라우저와 같은 인덱스 형식(index.jsonl)을 쓰고, 최근 MAX_SHOTS 장만 남긴다. 화면은 /api/browser/shots 로 목록을,
/api/browser/shots/image 로 이미지를 읽는다 (경로는 `local://<파일명>`).
"""
import json
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from app.config import settings

MAX_SHOTS = 60
PREFIX = "local://"
_NAME = re.compile(r"^\d{10,}\.jpg$")
_lock = threading.Lock()


def _dir(user_id: str) -> Path:
    base = Path(settings.LOCAL_SHOTS_DIR) if settings.LOCAL_SHOTS_DIR else Path(tempfile.gettempdir()) / "agent_local_shots"
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", user_id or "anon")[:64]
    return base / safe


def save(user_id: str, jpeg: bytes, url: str, title: str, run: Optional[str]) -> str:
    """스크린샷을 저장하고 `local://파일명` 경로를 돌려준다. 오래된 것은 지운다."""
    d = _dir(user_id)
    with _lock:
        d.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        while (d / f"{ts}.jpg").exists():  # 같은 ms 에 두 장이 저장돼도 겹치지 않게
            ts += 1
        name = f"{ts}.jpg"
        (d / name).write_bytes(jpeg)
        with (d / "index.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"f": PREFIX + name, "url": url[:500], "title": title[:200], "t": ts, "run": run}, ensure_ascii=False) + "\n")
        files = sorted(x.name for x in d.iterdir() if _NAME.match(x.name))
        for old in files[:-MAX_SHOTS]:
            (d / old).unlink(missing_ok=True)
        keep = {x.name for x in d.iterdir() if _NAME.match(x.name)}
        lines = [ln for ln in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if _row_name(ln) in keep]
        (d / "index.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return PREFIX + name


def _row_name(line: str) -> str:
    try:
        return str(json.loads(line)["f"])[len(PREFIX):]
    except (ValueError, KeyError, TypeError):
        return ""


def rows(user_id: str) -> list[dict]:
    """저장된 스크린샷 행 (오래된 것부터). 이미지가 사라진 행은 뺀다."""
    d = _dir(user_id)
    idx = d / "index.jsonl"
    if not idx.exists():
        return []
    out = []
    for ln in idx.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(ln)
            name = str(r["f"])[len(PREFIX):]
            if _NAME.match(name) and (d / name).exists():
                out.append({"f": str(r["f"]), "url": str(r.get("url", "")), "title": str(r.get("title", "")), "t": int(r["t"]), "run": r.get("run")})
        except (ValueError, KeyError, TypeError):
            continue
    return out


def image_path(user_id: str, name: str) -> Optional[Path]:
    """사용자의 스크린샷 파일 경로. 파일명이 형식에 맞지 않거나 없으면 None (경로 조작 방지)."""
    if not _NAME.match(name or ""):
        return None
    p = _dir(user_id) / name
    return p if p.is_file() else None

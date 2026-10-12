"""sandbox 파일을 공개 다운로드 링크로 발행한다.

파일은 {PUBLISH_DIR}/{token}/ 에 복사되고, 추측 불가능한 token 을 아는 사람만 만료 전까지
GET /api/files/{token}/{filename} 으로 내려받을 수 있다 (인증 없음 = 공개 링크).
"""
import json
import re
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from app.config import settings

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def safe_filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name.strip().lstrip(".")
    name = re.sub(r"[^\w.\- ()\[\]]", "_", name, flags=re.UNICODE)
    return name[:150] or "file"


def cleanup_expired() -> int:
    root = Path(settings.PUBLISH_DIR)
    if not root.is_dir():
        return 0
    removed = 0
    for d in root.iterdir():
        try:
            meta = json.loads((d / "meta.json").read_text())
            expired = datetime.fromisoformat(meta["expires_at"]) < _now()
        except Exception:
            expired = True  # 메타가 없거나 깨진 항목도 정리
        if expired:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


def publish(user_id: str, filename: str, data: bytes, expires_hours: Optional[int] = None) -> dict:
    max_bytes = settings.PUBLISH_MAX_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"발행 가능한 최대 크기는 {settings.PUBLISH_MAX_MB}MB 입니다")
    hours = min(max(expires_hours or settings.PUBLISH_EXPIRE_HOURS, 1), 24 * 7)

    cleanup_expired()
    name = safe_filename(filename)
    token = secrets.token_urlsafe(24)
    d = Path(settings.PUBLISH_DIR) / token
    d.mkdir(parents=True)
    (d / "file").write_bytes(data)
    expires_at = _now() + timedelta(hours=hours)
    (d / "meta.json").write_text(
        json.dumps({"user_id": user_id, "filename": name, "expires_at": expires_at.isoformat(), "size": len(data)})
    )
    url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/files/{token}/{quote(name)}"
    return {"url": url, "expires_at": expires_at.isoformat(), "filename": name, "size": len(data)}


def resolve(token: str, filename: str) -> Optional[tuple[Path, str]]:
    """유효한 (만료 전) 링크면 (파일 경로, 표시 파일명), 아니면 None."""
    if not TOKEN_RE.match(token):
        return None
    d = Path(settings.PUBLISH_DIR) / token
    try:
        meta = json.loads((d / "meta.json").read_text())
        if datetime.fromisoformat(meta["expires_at"]) < _now():
            shutil.rmtree(d, ignore_errors=True)
            return None
        if meta["filename"] != filename:
            return None
        return d / "file", meta["filename"]
    except Exception:
        return None

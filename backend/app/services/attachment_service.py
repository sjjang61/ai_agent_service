"""채팅 첨부 파일: sandbox 업로드 경로 검증과 에이전트에게 전달할 안내 문구 생성."""
import posixpath
from typing import Any, Iterable, Optional

from fastapi import HTTPException

from app.agent.prompts import render

UPLOAD_DIR = "/workspace/uploads"
MAX_ATTACHMENTS = 10


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def validate_attachments(raw: Optional[Iterable[Any]]) -> list[dict]:
    """클라이언트가 보낸 첨부 목록을 검증·정규화한다. 업로드 폴더 밖의 경로는 거부한다."""
    items = list(raw or [])
    if len(items) > MAX_ATTACHMENTS:
        raise HTTPException(status_code=400, detail=f"첨부 파일은 최대 {MAX_ATTACHMENTS}개까지 가능합니다")
    out = []
    for a in items:
        path = posixpath.normpath(str(getattr(a, "path", None) or (a.get("path") if isinstance(a, dict) else "")))
        if posixpath.dirname(path) != UPLOAD_DIR:
            raise HTTPException(status_code=400, detail=f"허용되지 않는 첨부 경로입니다: {path}")
        size = getattr(a, "size", None) if not isinstance(a, dict) else a.get("size")
        kind = getattr(a, "kind", None) if not isinstance(a, dict) else a.get("kind")
        count = getattr(a, "file_count", None) if not isinstance(a, dict) else a.get("file_count")
        item = {"name": posixpath.basename(path), "path": path, "size": int(size or 0)}
        if kind == "folder":
            item.update(kind="folder", file_count=int(count or 0))
        out.append(item)
    return out


def compose_with_attachments(content: str, attachments: Optional[list[dict]]) -> str:
    """사용자 입력에 첨부 파일 안내를 덧붙여 에이전트가 파일 위치를 알 수 있게 한다."""
    if not attachments:
        return content
    lines = []
    for a in attachments:
        size = _fmt_size(int(a.get("size", 0)))
        if a.get("kind") == "folder":
            lines.append(f"- {a['path']}/ (폴더, 파일 {int(a.get('file_count', 0))}개, {size})")
        else:
            lines.append(f"- {a['path']} ({size})")
    note = render("attachment_note", lines="\n".join(lines))
    return f"{content}\n\n{note}" if content else note

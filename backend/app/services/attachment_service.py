"""채팅 첨부 파일: sandbox 업로드 경로 검증과 에이전트에게 전달할 안내 문구 생성."""
import posixpath
from typing import Any, Iterable, Optional

from fastapi import HTTPException

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
        out.append({"name": posixpath.basename(path), "path": path, "size": int(size or 0)})
    return out


def compose_with_attachments(content: str, attachments: Optional[list[dict]]) -> str:
    """사용자 입력에 첨부 파일 안내를 덧붙여 에이전트가 파일 위치를 알 수 있게 한다."""
    if not attachments:
        return content
    lines = [f"- {a['path']} ({_fmt_size(int(a.get('size', 0)))})" for a in attachments]
    note = (
        "[첨부 파일 — sandbox 작업공간에 업로드됨]\n"
        + "\n".join(lines)
        + "\n(이미지는 read_image, 텍스트는 read_file, 그 외 형식은 exec_command 등으로 확인하세요)"
    )
    return f"{content}\n\n{note}" if content else note

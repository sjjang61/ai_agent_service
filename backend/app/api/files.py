from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import publish_service

router = APIRouter()


@router.get("/{token}/{filename}")
async def download_published(token: str, filename: str):
    """공개 다운로드 링크 (인증 없음, 만료 시 404). 항상 attachment 로 내려보낸다."""
    found = publish_service.resolve(token, filename)
    if not found:
        raise HTTPException(status_code=404, detail="Link not found or expired")
    path, name = found
    return FileResponse(
        path,
        filename=name,
        media_type="application/octet-stream",  # 브라우저가 HTML 등을 이 도메인에서 렌더링하지 못하게 함
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=0"},
    )

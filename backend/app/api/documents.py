"""
문서 업로드 및 관리 API
"""

import os
import uuid
import tempfile
from typing import List

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.services.rag_service import RAGService
from app.config import settings

router = APIRouter()


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    total_chunks: int
    created_at: str
    error_message: str | None = None


@router.post("/conversations/{conversation_id}/documents", response_model=DocumentResponse)
async def upload_document(
    conversation_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """대화에 문서 업로드 및 인덱싱"""

    # 1. 파일 타입 검증
    if not file.filename:
        raise HTTPException(400, "파일 이름이 없습니다.")

    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ("txt", "md", "pdf"):
        raise HTTPException(400, f"지원하지 않는 파일 형식입니다: {file_ext}")

    # 2. 파일 크기 검증
    content = await file.read()
    file_size = len(content)

    max_size = settings.RAG_MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(400, f"파일 크기는 {settings.RAG_MAX_FILE_SIZE_MB}MB 이하여야 합니다.")

    # 3. 임시 파일에 저장
    file_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{file_id}.{file_ext}")

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        # 4. 인덱싱
        document = await RAGService.index_document(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
            file_path=temp_path,
            original_filename=file.filename,
        )

        return DocumentResponse(
            id=document.id,
            filename=document.original_filename,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            total_chunks=document.total_chunks,
            created_at=document.created_at.isoformat(),
            error_message=document.error_message,
        )

    except Exception as e:
        # 임시 파일 정리
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(500, f"문서 인덱싱 실패: {str(e)}")


@router.get("/conversations/{conversation_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    conversation_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """대화의 문서 목록 조회"""
    result = await db.execute(
        select(Document)
        .where(Document.conversation_id == conversation_id)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()

    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.original_filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            total_chunks=doc.total_chunks,
            created_at=doc.created_at.isoformat(),
            error_message=doc.error_message,
        )
        for doc in documents
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """문서 삭제"""
    # 문서 조회 및 권한 확인
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    if doc.user_id != current_user.id:
        raise HTTPException(403, "권한이 없습니다.")

    # 문서 삭제 (DB + 벡터 스토어)
    await RAGService.delete_document(db, document_id, doc.conversation_id)

    # 임시 파일 정리
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    return {"success": True}

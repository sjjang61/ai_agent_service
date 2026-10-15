"""
RAG 핵심 로직: 문서 인덱싱 및 검색
"""

import os
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.document_parser import DocumentParser
from app.services.document_chunker import DocumentChunker
from app.core.vector_store import VectorStoreManager


class RAGService:
    """RAG 핵심 로직: 문서 인덱싱 및 검색"""

    @staticmethod
    async def index_document(
        db: AsyncSession,
        conversation_id: str,
        user_id: str,
        file_path: str,
        original_filename: str,
    ) -> Document:
        """파일 → 임베딩 → 벡터 DB 저장"""

        # 1. 파일 정보
        file_size = os.path.getsize(file_path)
        file_type = original_filename.split(".")[-1].lower()

        # 2. Document 레코드 생성
        doc = Document(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            user_id=user_id,
            filename=str(uuid.uuid4()),
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            status="processing",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        try:
            # 3. 텍스트 추출
            with open(file_path, "rb") as f:
                text = DocumentParser.parse(f, file_type)

            # 4. 청킹
            chunker = DocumentChunker()
            chunks = chunker.chunk(
                text,
                metadata={
                    "document_id": doc.id,
                    "filename": original_filename,
                },
            )

            # 5. Chroma에 저장
            vector_store = VectorStoreManager.get_collection(conversation_id)
            texts = [c["content"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            ids = [f"{doc.id}_{i}" for i in range(len(chunks))]

            vector_store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids,
            )

            # 6. DocumentChunk 레코드 생성
            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk["content"],
                    embedding_id=ids[i],
                    metadata=chunk["metadata"],
                )
                db.add(db_chunk)

            # 7. 상태 업데이트
            doc.status = "completed"
            doc.total_chunks = len(chunks)
            await db.commit()
            await db.refresh(doc)

            return doc

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            await db.commit()
            raise

    @staticmethod
    async def search_documents(
        conversation_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """의미적 검색"""
        try:
            vector_store = VectorStoreManager.get_collection(conversation_id)

            results = vector_store.similarity_search_with_score(
                query=query,
                k=top_k,
            )

            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
                for doc, score in results
            ]
        except Exception:
            # 컬렉션이 없거나 문서가 없는 경우 빈 리스트 반환
            return []

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        document_id: str,
        conversation_id: str,
    ):
        """문서 삭제 (DB + 벡터 스토어)"""
        # 1. DocumentChunk 조회
        result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        chunks = result.scalars().all()

        # 2. Chroma에서 삭제
        if chunks:
            try:
                vector_store = VectorStoreManager.get_collection(conversation_id)
                embedding_ids = [c.embedding_id for c in chunks]
                vector_store.delete(ids=embedding_ids)
            except Exception:
                pass  # 벡터 스토어 삭제 실패해도 계속 진행

        # 3. DB 레코드 삭제 (CASCADE로 자동 삭제되지만 명시)
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await db.execute(delete(Document).where(Document.id == document_id))
        await db.commit()

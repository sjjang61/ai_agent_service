"""
문서를 청크로 분할
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings


class DocumentChunker:
    """문서를 청크로 분할"""

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def chunk(self, text: str, metadata: dict = None) -> list[dict]:
        """텍스트 → 청크 목록"""
        chunks = self.splitter.split_text(text)

        return [
            {
                "content": chunk,
                "metadata": {
                    **(metadata or {}),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            }
            for i, chunk in enumerate(chunks)
        ]

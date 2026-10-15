"""
Chroma 벡터 스토어 관리자
"""

import os
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from app.config import settings


class VectorStoreManager:
    """Chroma 벡터 스토어 관리자"""

    _client: Optional[chromadb.Client] = None

    @classmethod
    def initialize(cls):
        """Chroma 클라이언트 초기화 (앱 시작 시)"""
        # Chroma persist 디렉토리 생성
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

        cls._client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    @classmethod
    def get_client(cls) -> chromadb.Client:
        """Chroma 클라이언트 반환"""
        if cls._client is None:
            cls.initialize()
        return cls._client

    @classmethod
    def get_collection(cls, conversation_id: str) -> Chroma:
        """대화별 Chroma 컬렉션 반환"""
        collection_name = f"conv_{conversation_id.replace('-', '_')}"

        embedding_function = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
        )

        return Chroma(
            client=cls.get_client(),
            collection_name=collection_name,
            embedding_function=embedding_function,
        )

    @classmethod
    def delete_collection(cls, conversation_id: str):
        """대화 삭제 시 벡터 컬렉션도 삭제"""
        collection_name = f"conv_{conversation_id.replace('-', '_')}"
        try:
            cls.get_client().delete_collection(collection_name)
        except Exception:
            pass  # 컬렉션이 없으면 무시

    @classmethod
    async def cleanup(cls):
        """종료 시 정리"""
        # Chroma 클라이언트는 자동으로 정리됨
        cls._client = None

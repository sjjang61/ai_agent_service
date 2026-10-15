"""RAG tool for searching uploaded documents"""

from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from app.services.rag_service import RAGService
from app.config import settings


class SearchDocumentsInput(BaseModel):
    query: str = Field(description="검색 쿼리 (한글 또는 영어)")
    top_k: Optional[int] = Field(
        default=None,
        description=f"상위 K개 결과 (기본값: {settings.RAG_TOP_K})",
    )


class RAGTool(BaseTool):
    """업로드된 문서에서 정보 검색하는 도구"""

    name: str = "search_documents"
    description: str = """현재 대화에 업로드된 문서에서 관련 정보를 검색합니다.
사용자가 업로드한 PDF, 텍스트 파일 등에서 의미적으로 유사한 내용을 찾습니다.

사용 시기:
- 사용자가 업로드한 문서에 대해 질문할 때
- 문서 내용 요약이 필요할 때
- 특정 정보를 문서에서 찾아야 할 때
- "문서에서", "업로드한 파일에서" 같은 표현이 있을 때

예시:
- query: "핵심 내용", top_k: 3
- query: "주요 결론", top_k: 5
- query: "introduction", top_k: 3
"""
    args_schema: type[BaseModel] = SearchDocumentsInput
    conversation_id: str

    def _run(self, query: str, top_k: Optional[int] = None) -> str:
        """동기 실행은 지원하지 않음"""
        raise NotImplementedError("RAGTool은 비동기 실행만 지원합니다. _arun을 사용하세요.")

    async def _arun(self, query: str, top_k: Optional[int] = None) -> str:
        """문서 검색 실행"""
        k = top_k or settings.RAG_TOP_K

        results = await RAGService.search_documents(
            conversation_id=self.conversation_id,
            query=query,
            top_k=k,
        )

        if not results:
            return "업로드된 문서가 없거나 관련 정보를 찾을 수 없습니다."

        # 결과 포맷팅
        output = [f"검색 결과 (쿼리: '{query}'):\n"]
        for i, result in enumerate(results, 1):
            metadata = result["metadata"]
            filename = metadata.get("filename", "Unknown")
            score = result["score"]
            content = result["content"]

            output.append(f"\n[{i}] 출처: {filename} (관련도: {score:.3f})")
            output.append(f"내용: {content[:800]}...")
            output.append("")

        return "\n".join(output)

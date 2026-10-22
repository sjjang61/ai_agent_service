"""search_wiki: 사용자의 개인 위키(저장해 둔 정리 문서)에서 관련 내용을 찾는다."""
from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool

MAX_EXCERPT = 1500


class SearchWikiInput(BaseModel):
    query: str = Field(description="찾을 주제나 질문 (한국어/영어 키워드가 들어간 문장)")
    limit: int = Field(default=3, ge=1, le=5, description="가져올 문서 수 (기본 3, 최대 5)")


class SearchWikiTool(BaseTool):
    name: str = "search_wiki"
    description: str = (
        "사용자가 이전 대화에서 저장해 둔 개인 위키 문서(정리된 지식)를 검색합니다. "
        "사용자가 '내 위키', '저장해 둔', '전에 정리한', '내가 모아둔' 같은 표현으로 자신의 자료를 가리키거나, "
        "질문이 사용자가 이미 정리해 둔 주제일 가능성이 있을 때 먼저 호출하세요. "
        "결과는 제목·요약·본문 발췌·연결된 문서이며, 답변에 활용할 때는 위키 문서 제목을 출처로 밝히세요. "
        "위키에 없으면 다른 도구(웹 검색 등)를 쓰세요. 위키 내용이 오래됐을 수 있으니 최신 정보가 필요한 질문은 웹 검색으로 확인하세요."
    )
    args_schema: type[BaseModel] = SearchWikiInput
    user_id: str = ""

    def _run(self, query: str, limit: int = 3) -> str:
        return "search_wiki supports async execution only"

    async def _arun(self, query: str, limit: int = 3) -> str:
        from app.db.session import AsyncSessionLocal
        from app.services.wiki_service import WikiService

        async with AsyncSessionLocal() as db:
            entries = await WikiService.search_for_agent(self.user_id, query, db, limit=min(max(limit, 1), 5))
            titles, out, _ = await WikiService.link_graph(self.user_id, db)
        if not entries:
            return "위키에서 관련 문서를 찾지 못했습니다."
        blocks = []
        for e in entries:
            related = ", ".join(titles[i] for i in out.get(e.id, [])[:5])
            body = (e.content or "")[:MAX_EXCERPT] + ("…" if len(e.content or "") > MAX_EXCERPT else "")
            blocks.append(
                f"### {e.title}  (카테고리: {e.category}, 태그: {', '.join(e.tags or []) or '-'}, 수정: {e.updated_at:%Y-%m-%d})\n"
                + (f"요약: {e.summary}\n" if e.summary else "")
                + (f"연결된 문서: {related}\n" if related else "")
                + f"\n{body}"
            )
        return "\n\n---\n\n".join(blocks)

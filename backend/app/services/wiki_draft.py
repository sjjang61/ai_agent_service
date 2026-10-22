"""선택한 텍스트를 위키 문서로 정리한다 (제목·요약·마크다운 본문·카테고리·태그). 프롬프트는 prompts/wiki_article.md."""
import asyncio
import json
import logging
import re
from typing import Optional

from app.agent.prompts import render
from app.schemas.wiki import WikiDraftResponse, WikiLinkRef

logger = logging.getLogger(__name__)

DRAFT_TIMEOUT_SECONDS = 60
INPUT_CLIP = 12000
CATEGORIES = ("general", "work", "learning", "reference")


def parse_draft(text: str, source: str) -> Optional[WikiDraftResponse]:
    """LLM 응답(JSON)을 검증해 정리한다. 제목이나 본문이 없으면 None."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    title = " ".join(str(data.get("title") or "").split())[:100]
    content = str(data.get("content") or "").strip()
    if not title or not content:
        return None
    category = data.get("category") if data.get("category") in CATEGORIES else "general"
    raw_tags = data.get("tags") if isinstance(data.get("tags"), list) else []
    tags = []
    for t in raw_tags:
        t = str(t).strip().lstrip("#")[:30]
        if t and t not in tags:
            tags.append(t)
    summary = " ".join(str(data.get("summary") or "").split())[:300]
    return WikiDraftResponse(title=title, summary=summary, content=content, category=category, tags=tags[:6])


MAX_CANDIDATES = 80
RELATED_HEADING = "## 관련 문서"


def parse_match(text: str, valid_ids: set) -> tuple:
    """(합칠 문서 id 또는 None, 관련 문서 id 목록). 목록에 없는 id 는 버린다."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None, []
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None, []
    if not isinstance(data, dict):
        return None, []
    merge = data.get("merge_into") if data.get("merge_into") in valid_ids else None
    raw = data.get("related") if isinstance(data.get("related"), list) else []
    related = [i for i in dict.fromkeys(raw) if i in valid_ids and i != merge][:5]
    return merge, related


def with_related_section(content: str, titles: list) -> str:
    """본문 끝의 '## 관련 문서' 절에 [[제목]] 링크를 (아직 없는 것만) 붙인다. 링크는 LLM 이 아니라 코드가 만든다."""
    content = re.sub(r"\n+" + re.escape(RELATED_HEADING) + r"\s*$", "", content)  # 내용 없이 제목만 남은 절은 지운다
    missing = [t for t in titles if f"[[{t}]]" not in content]
    if not missing:
        return content
    lines = "\n".join(f"- [[{t}]]" for t in missing)
    if RELATED_HEADING in content:
        head, _, tail = content.partition(RELATED_HEADING)
        return head + RELATED_HEADING + "\n" + tail.strip("\n") + ("\n" if tail.strip() else "") + lines
    return content.rstrip() + "\n\n" + RELATED_HEADING + "\n" + lines


async def _ask(llm, prompt: str) -> str:
    from app.services.memory_extractor import _content_text

    resp = await asyncio.wait_for(llm.ainvoke(prompt), DRAFT_TIMEOUT_SECONDS)
    return _content_text(resp.content)


async def draft_article(selected_text: str, entries: Optional[list] = None, allow_merge: bool = True) -> Optional[WikiDraftResponse]:
    """entries: 내 기존 위키 문서들 [{id,title,summary,tags,content}]. 있으면 같은 주제의 문서에 합칠지, 관련 문서가 무엇인지도 판단한다."""
    try:
        from app.agent.react_agent import AgentRunner

        llm = AgentRunner(tools=[]).llm
        text = selected_text[:INPUT_CLIP]
        by_id = {e["id"]: e for e in (entries or [])[:MAX_CANDIDATES]}
        merge_id, related_ids = None, []
        if by_id:
            try:  # 관련 문서 판단이 실패해도 새 문서로 정리는 계속한다
                listing = "\n".join(
                    f"{e['id']} | {e['title']} | {(e.get('summary') or '')[:100]} | {', '.join(e.get('tags') or [])}"
                    for e in by_id.values()
                )
                merge_id, related_ids = parse_match(await _ask(llm, render("wiki_match", text=text[:4000], entries=listing)), set(by_id))
            except Exception as e:  # noqa: BLE001
                logger.warning("[wiki] 관련 문서 판단 실패: %s", e)
        if merge_id and not allow_merge:  # 합치지 않기로 했으면 그 문서는 관련 문서로 남긴다
            related_ids, merge_id = [merge_id, *related_ids][:5], None
        if merge_id:
            base = by_id[merge_id]
            raw = await _ask(
                llm, render("wiki_merge", existing_title=base["title"], existing_content=base["content"][:INPUT_CLIP], text=text)
            )
        else:
            raw = await _ask(llm, render("wiki_article", text=text))
        draft = parse_draft(raw, selected_text)
        if draft is None:
            return None
        titles = [by_id[i]["title"] for i in related_ids]
        draft.content = with_related_section(draft.content, titles)
        draft.related = [WikiLinkRef(id=i, title=by_id[i]["title"]) for i in related_ids]
        if merge_id:
            draft.merge_into = WikiLinkRef(id=merge_id, title=by_id[merge_id]["title"])
        return draft
    except Exception as e:
        logger.warning("[wiki] 문서 정리 실패: %s", e)
        return None

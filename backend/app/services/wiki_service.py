"""Wiki service for CRUD operations."""

import difflib
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wiki_entry import WikiEntry
from app.schemas.wiki import (
    WikiEntryCreate, WikiEntryUpdate, WikiLinkRef, WikiLintIssue, WikiLintReport, WikiMergeRequest, WikiSearchParams,
)

STALE_DAYS = 90


def _norm_title(t: str) -> str:
    return re.sub(r"[\s\-_·.,()\[\]]+", "", (t or "").lower())


class WikiService:
    """Wiki entry CRUD operations."""

    @staticmethod
    async def list_entries(
        user_id: str,
        params: WikiSearchParams,
        db: AsyncSession,
    ) -> List[WikiEntry]:
        """List wiki entries with optional filtering."""
        query = select(WikiEntry).where(WikiEntry.user_id == user_id)

        # Category filter
        if params.category:
            query = query.where(WikiEntry.category == params.category)

        # Tags filter (if any tag matches)
        # Note: This is a simple Python-level filter after query
        # For production, consider using JSON operators for better performance

        # Keyword search in title and content
        if params.query:
            pattern = f"%{params.query}%"
            query = query.where(
                or_(
                    WikiEntry.title.ilike(pattern),
                    WikiEntry.content.ilike(pattern),
                )
            )

        # Order by most recent first
        query = query.order_by(WikiEntry.updated_at.desc(), WikiEntry.created_at.desc())
        query = query.offset(params.offset).limit(params.limit)

        result = await db.execute(query)
        entries = list(result.scalars().all())

        # Filter by tags in Python if needed
        if params.tags:
            entries = [
                e for e in entries
                if any(tag in (e.tags or []) for tag in params.tags)
            ]

        return entries

    @staticmethod
    async def get_entry(
        user_id: str, entry_id: str, db: AsyncSession
    ) -> Optional[WikiEntry]:
        """Get a single wiki entry by ID."""
        result = await db.execute(
            select(WikiEntry).where(
                WikiEntry.id == entry_id,
                WikiEntry.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_entry(
        user_id: str,
        data: WikiEntryCreate,
        db: AsyncSession,
    ) -> WikiEntry:
        """Create a new wiki entry."""
        links = await WikiService._valid_links(user_id, data.links, db)
        entry = WikiEntry(
            user_id=user_id,
            links=links,
            title=data.title,
            content=data.content,
            category=data.category,
            tags=data.tags,
            summary=data.summary,
            source_text=data.source_text,
            source_message_id=data.source_message_id,
            source_conversation_id=data.source_conversation_id,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def update_entry(
        user_id: str,
        entry_id: str,
        data: WikiEntryUpdate,
        db: AsyncSession,
    ) -> Optional[WikiEntry]:
        """Update an existing wiki entry."""
        entry = await WikiService.get_entry(user_id, entry_id, db)
        if not entry:
            return None

        changes = data.model_dump(exclude_none=True)
        if "links" in changes:
            changes["links"] = await WikiService._valid_links(user_id, changes["links"], db, exclude=entry.id)
        for k, v in changes.items():
            setattr(entry, k, v)

        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def delete_entry(
        user_id: str, entry_id: str, db: AsyncSession
    ) -> bool:
        """Delete a wiki entry."""
        result = await db.execute(
            delete(WikiEntry).where(
                WikiEntry.id == entry_id,
                WikiEntry.user_id == user_id,
            )
        )
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def search_entries(
        user_id: str,
        query_text: str,
        db: AsyncSession,
        limit: int = 20,
    ) -> List[WikiEntry]:
        """Full-text search in wiki entries."""
        pattern = f"%{query_text}%"
        result = await db.execute(
            select(WikiEntry)
            .where(
                WikiEntry.user_id == user_id,
                or_(
                    WikiEntry.title.ilike(pattern),
                    WikiEntry.content.ilike(pattern),
                ),
            )
            .order_by(WikiEntry.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── 문서 간 연결 ──────────────────────────────────────────────────────────
    @staticmethod
    async def _valid_links(user_id: str, ids: List[str], db: AsyncSession, exclude: Optional[str] = None) -> List[str]:
        """내 문서의 id 만 남긴다 (남의 문서·없는 문서·자기 자신 제외, 중복 제거)."""
        wanted = [i for i in dict.fromkeys(ids or []) if i != exclude]
        if not wanted:
            return []
        r = await db.execute(select(WikiEntry.id).where(WikiEntry.user_id == user_id, WikiEntry.id.in_(wanted)))
        ok = set(r.scalars().all())
        return [i for i in wanted if i in ok]

    @staticmethod
    async def link_graph(user_id: str, db: AsyncSession) -> Tuple[Dict[str, str], Dict[str, List[str]], Dict[str, List[str]]]:
        """(id→제목, id→연결한 문서 id, id→이 문서를 연결한 문서 id). 삭제돼 없어진 문서는 제외한다."""
        r = await db.execute(select(WikiEntry.id, WikiEntry.title, WikiEntry.links).where(WikiEntry.user_id == user_id))
        rows = r.all()
        titles = {i: t for i, t, _ in rows}
        out: Dict[str, List[str]] = {i: [x for x in (links or []) if x in titles and x != i] for i, _, links in rows}
        back: Dict[str, List[str]] = {i: [] for i in titles}
        for src, targets in out.items():
            for t in targets:
                back[t].append(src)
        return titles, out, back

    @staticmethod
    async def merge_entry(user_id: str, entry_id: str, data: WikiMergeRequest, db: AsyncSession) -> Optional[WikiEntry]:
        """기존 문서에 새 내용을 합친 결과(정리된 본문)를 반영한다. 태그·연결은 합집합, 원문은 이어 붙인다."""
        entry = await WikiService.get_entry(user_id, entry_id, db)
        if not entry:
            return None
        entry.content = data.content
        if data.summary:
            entry.summary = data.summary
        entry.tags = list(dict.fromkeys([*(entry.tags or []), *data.tags]))[:12]
        entry.links = await WikiService._valid_links(user_id, [*(entry.links or []), *data.add_links], db, exclude=entry.id)
        if data.new_source_text:
            entry.source_text = (entry.source_text + "\n\n---\n\n" if entry.source_text else "") + data.new_source_text
        await db.commit()
        await db.refresh(entry)
        return entry

    # ── 에이전트용 검색 ───────────────────────────────────────────────────────
    @staticmethod
    async def search_for_agent(user_id: str, query: str, db: AsyncSession, limit: int = 5) -> List[WikiEntry]:
        """질문 문장에서 키워드를 뽑아 제목·본문·요약에서 찾고, 제목에 맞을수록 앞에 둔다."""
        tokens = [t for t in dict.fromkeys(re.findall(r"[\w가-힣]{2,}", query.lower()))][:8]
        if not tokens:
            return []
        conds = []
        for t in tokens:
            p = f"%{t}%"
            conds += [WikiEntry.title.ilike(p), WikiEntry.content.ilike(p), WikiEntry.summary.ilike(p)]
        r = await db.execute(select(WikiEntry).where(WikiEntry.user_id == user_id, or_(*conds)).limit(60))
        rows = list(r.scalars().all())

        def score(e: WikiEntry) -> int:
            title, body = (e.title or "").lower(), ((e.summary or "") + " " + (e.content or "")).lower()
            tags = " ".join(e.tags or []).lower()
            return sum(3 * (t in title) + 2 * (t in tags) + (t in body) for t in tokens)

        rows.sort(key=score, reverse=True)
        return rows[:limit]

    # ── 점검(lint) ────────────────────────────────────────────────────────────
    @staticmethod
    async def lint(user_id: str, db: AsyncSession) -> WikiLintReport:
        """중복·오래된·고아·깨진 연결·요약 없는 문서를 찾는다 (LLM 없이 규칙으로)."""
        r = await db.execute(select(WikiEntry).where(WikiEntry.user_id == user_id).order_by(WikiEntry.updated_at.desc()))
        entries = list(r.scalars().all())
        titles, out, back = await WikiService.link_graph(user_id, db)
        ref = lambda e: WikiLinkRef(id=e.id, title=e.title)  # noqa: E731
        issues: List[WikiLintIssue] = []

        # 중복 후보: 제목이 거의 같거나, 같은 카테고리에서 태그가 대부분 겹침
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                ratio = difflib.SequenceMatcher(None, _norm_title(a.title), _norm_title(b.title)).ratio()
                ta, tb = set(a.tags or []), set(b.tags or [])
                tag_sim = len(ta & tb) / len(ta | tb) if ta and tb else 0
                if ratio >= 0.8 or (a.category == b.category and tag_sim >= 0.6 and len(ta & tb) >= 2):
                    why = "제목이 거의 같습니다" if ratio >= 0.8 else "태그가 대부분 겹칩니다"
                    issues.append(WikiLintIssue(type="duplicate", message=f"중복일 수 있습니다: {why}. 합치는 것을 검토하세요.", entries=[ref(a), ref(b)]))

        limit = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
        for e in entries:
            updated = e.updated_at.replace(tzinfo=timezone.utc) if e.updated_at and e.updated_at.tzinfo is None else e.updated_at
            if updated and updated < limit:
                issues.append(WikiLintIssue(type="stale", message=f"{STALE_DAYS}일 넘게 수정되지 않았습니다. 내용이 오래됐는지 확인하세요.", entries=[ref(e)]))
            if not (e.summary or "").strip():
                issues.append(WikiLintIssue(type="no_summary", message="요약이 없습니다.", entries=[ref(e)]))
            broken = [x for x in (e.links or []) if x not in titles]
            if broken:
                issues.append(WikiLintIssue(type="broken_link", message=f"삭제된 문서로 연결된 링크 {len(broken)}개가 있습니다.", entries=[ref(e)]))
            if len(entries) >= 3 and not out.get(e.id) and not back.get(e.id):
                issues.append(WikiLintIssue(type="orphan", message="다른 문서와 연결되어 있지 않습니다.", entries=[ref(e)]))
        return WikiLintReport(total=len(entries), issues=issues)

"""위키 문서를 지식화한다: LLM 으로 개체·개념·관계를 뽑아 노드(스텁 문서)와 간선(wiki_edges)으로 저장. 프롬프트: prompts/wiki_graph_extract.md.

저장·수정·병합 후 백그라운드로 실행된다(WIKI_GRAPH_AUTO). 본문 해시가 같으면 건너뛴다.
엔티티 판정은 정규화한 이름·별칭이 기존 문서와 같은지로 먼저 하고, 새 대상이면 AI 스텁 문서(auto_generated)를 만든다.
"""
import asyncio
import hashlib
import json
import logging
import re
from typing import Optional

from sqlalchemy import delete, select

from app.agent.prompts import render
from app.config import settings
from app.models.wiki_entry import WikiEdge, WikiEntry

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 90
MAX_ENTITIES = 15
MAX_RELATIONS = 25
INPUT_CLIP = 12000
_locks: dict = {}  # 사용자별 직렬화 — 동시에 돌면 서로의 새 개체를 못 봐서 같은 개체가 중복 생성된다
_tasks: set = set()


def norm(name: str) -> str:
    return re.sub(r"[\s\-_·.,()\[\]/]+", "", (name or "").lower())


def content_hash(title: str, content: str) -> str:
    return hashlib.sha1(f"{title}\n{content}".encode()).hexdigest()


def parse_extraction(text: str) -> tuple[list, list]:
    """LLM 응답 → (entities, relations). 이름 없는 항목·중복·존재하지 않는 대상을 가리키는 관계는 버린다."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        data = json.loads(m.group()) if m else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return [], []
    ents, seen = [], set()
    for e in data.get("entities") or []:
        if not isinstance(e, dict):
            continue
        name = " ".join(str(e.get("name") or "").split())[:100]
        if not name or norm(name) in seen:
            continue
        seen.add(norm(name))
        aliases, anorm = [], {norm(name)}
        for x in e.get("aliases") or []:
            a = " ".join(str(x).split())[:100]
            if a and norm(a) not in anorm:
                anorm.add(norm(a))
                aliases.append(a)
        aliases = aliases[:6]
        ents.append({
            "name": name,
            "type": "concept" if e.get("type") == "concept" else "entity",
            "aliases": aliases,
            "summary": " ".join(str(e.get("summary") or "").split())[:300],
        })
        if len(ents) >= MAX_ENTITIES:
            break
    by_norm = {norm(e["name"]): e["name"] for e in ents}
    for e in ents:
        for a in e["aliases"]:
            by_norm.setdefault(norm(a), e["name"])
    rels, rseen = [], set()
    for r in data.get("relations") or []:
        if not isinstance(r, dict):
            continue
        s, t = by_norm.get(norm(str(r.get("source") or ""))), by_norm.get(norm(str(r.get("target") or "")))
        label = " ".join(str(r.get("label") or "").split())[:60]
        if not s or not t or s == t or (s, t, label) in rseen:
            continue
        rseen.add((s, t, label))
        rels.append({"source": s, "target": t, "label": label})
        if len(rels) >= MAX_RELATIONS:
            break
    return ents, rels


async def _ask(prompt: str) -> str:
    from app.agent.react_agent import AgentRunner
    from app.services.memory_extractor import _content_text

    resp = await asyncio.wait_for(AgentRunner(tools=[]).llm.ainvoke(prompt), LLM_TIMEOUT_SECONDS)
    return _content_text(resp.content)


async def knowledgeize(user_id: str, entry_id: str, force: bool = False) -> Optional[str]:
    """한 문서를 지식화한다. 반환: 'done' | 'skipped' | 'failed' (문서가 없으면 None)."""
    from app.db.session import AsyncSessionLocal

    async with _locks.setdefault(user_id, asyncio.Lock()):
        async with AsyncSessionLocal() as db:
            entry = (await db.execute(select(WikiEntry).where(WikiEntry.id == entry_id, WikiEntry.user_id == user_id))).scalar_one_or_none()
            if not entry:
                return None
            if entry.auto_generated:  # AI 스텁은 지식화하지 않는다 (재귀 방지)
                return "skipped"
            h = content_hash(entry.title, entry.content)
            if not force and entry.graph_hash == h and entry.graph_status == "done":
                return "skipped"
            try:
                raw = await _ask(render("wiki_graph_extract", title=entry.title, content=entry.content[:INPUT_CLIP],
                                        max_entities=MAX_ENTITIES, max_relations=MAX_RELATIONS))
                ents, rels = parse_extraction(raw)
                await _apply(db, user_id, entry, ents, rels)
                entry.graph_hash, entry.graph_status = h, "done"
                await db.commit()
                return "done"
            except Exception as e:  # noqa: BLE001
                logger.warning("[wiki-graph] 지식화 실패 (%s): %s: %s", entry_id[:8], type(e).__name__, str(e)[:200])
                await db.rollback()
                entry = (await db.execute(select(WikiEntry).where(WikiEntry.id == entry_id))).scalar_one_or_none()
                if entry:
                    entry.graph_status = "failed"
                    await db.commit()
                return "failed"


async def _apply(db, user_id: str, entry: WikiEntry, ents: list, rels: list):
    """추출 결과를 반영한다. 이 문서가 전에 만든 간선은 지우고 새로 만든다."""
    await db.execute(delete(WikiEdge).where(WikiEdge.user_id == user_id, WikiEdge.origin_id == entry.id))
    rows = (await db.execute(select(WikiEntry).where(WikiEntry.user_id == user_id))).scalars().all()
    index: dict = {}
    for r in rows:
        index.setdefault(norm(r.title), r)
        for a in r.aliases or []:
            index.setdefault(norm(a), r)
    ids: dict = {}
    for e in ents:
        found = index.get(norm(e["name"])) or next((index[norm(a)] for a in e["aliases"] if norm(a) in index), None)
        if found is None:
            found = WikiEntry(
                user_id=user_id, title=e["name"], content=(e["summary"] or e["name"]), summary=e["summary"] or None,
                node_type=e["type"], aliases=e["aliases"], auto_generated=True, category="general", tags=[],
                graph_status="done",
            )
            db.add(found)
            await db.flush()
            index[norm(found.title)] = found
            for a in found.aliases or []:
                index.setdefault(norm(a), found)
        elif e["aliases"] and found.auto_generated:  # 스텁이면 새로 알게 된 별칭을 보태 둔다
            found.aliases = list(dict.fromkeys([*(found.aliases or []), *e["aliases"]]))[:10]
        ids[e["name"]] = found.id
    seen = set()
    for name, eid in ids.items():
        if eid != entry.id and (entry.id, eid, "mentions") not in seen:
            seen.add((entry.id, eid, "mentions"))
            db.add(WikiEdge(user_id=user_id, src_id=entry.id, dst_id=eid, relation="언급", kind="mentions", origin_id=entry.id))
    for r in rels:
        s, t = ids.get(r["source"]), ids.get(r["target"])
        if s and t and s != t and (s, t, r["label"]) not in seen:
            seen.add((s, t, r["label"]))
            db.add(WikiEdge(user_id=user_id, src_id=s, dst_id=t, relation=r["label"], kind="extracted", origin_id=entry.id))
    await db.flush()
    await _prune_stubs(db, user_id)


async def _prune_stubs(db, user_id: str):
    """어떤 간선에도 쓰이지 않는 AI 스텁 문서(전에 추출됐다가 사라진 개체)를 지운다."""
    used = set((await db.execute(select(WikiEdge.src_id).where(WikiEdge.user_id == user_id))).scalars().all())
    used |= set((await db.execute(select(WikiEdge.dst_id).where(WikiEdge.user_id == user_id))).scalars().all())
    stubs = (await db.execute(select(WikiEntry).where(WikiEntry.user_id == user_id, WikiEntry.auto_generated.is_(True)))).scalars().all()
    for s in stubs:
        if s.id not in used:
            await db.delete(s)


def schedule(user_id: str, entry_id: str, force: bool = False):
    """백그라운드로 지식화를 시작한다 (실행 중인 이벤트 루프에서 호출)."""
    t = asyncio.create_task(knowledgeize(user_id, entry_id, force))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def schedule_many(user_id: str, entry_ids: list, force: bool = False):
    async def run():
        for i in entry_ids:
            await knowledgeize(user_id, i, force)

    t = asyncio.create_task(run())
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)

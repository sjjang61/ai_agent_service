"""위키 지식 그래프: 노드(문서)·간선 조회, 커뮤니티 탐지, 인사이트.

간선은 두 곳에서 모은다: 문서의 links(사용자가 만든 [[연결]], kind=link)와 wiki_edges(AI 가 추출한 mentions/extracted/similar).
커뮤니티는 라벨 전파로 구한다(순수 파이썬, 결정적 순서).
"""
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wiki_entry import WikiEdge, WikiEntry
from app.schemas.wiki import GraphEdge, GraphInsight, GraphInsights, GraphNode, GraphResponse, WikiLinkRef

NODE_TYPES = ("source", "entity", "concept", "overview", "other")
MAX_NODES = 1500


def detect_communities(ids: List[str], adj: Dict[str, Set[str]], rounds: int = 12) -> Dict[str, int]:
    """라벨 전파. 반환: id → 커뮤니티 번호(크기 큰 순으로 0,1,2…). 연결 없는 노드는 각자 하나."""
    label = {i: i for i in ids}
    order = sorted(ids)
    for _ in range(rounds):
        changed = False
        for n in order:
            nbrs = adj.get(n)
            if not nbrs:
                continue
            counts = Counter(label[m] for m in nbrs)
            best = max(counts.values())
            choice = min(l for l, c in counts.items() if c == best)
            if label[n] != choice and counts.get(label[n], 0) < best:
                label[n] = choice
                changed = True
        if not changed:
            break
    sizes = Counter(label.values())
    ranked = sorted(sizes, key=lambda l: (-sizes[l], l))
    num = {l: i for i, l in enumerate(ranked)}
    return {i: num[label[i]] for i in ids}


async def collect_edges(user_id: str, db: AsyncSession, titles: Optional[Dict[str, str]] = None, links: Optional[Dict[str, list]] = None) -> List[GraphEdge]:
    """link 간선(문서 links) + wiki_edges. (src,dst) 쌍·종류별로 합쳐 두 문서 사이의 중복 선을 줄인다."""
    if titles is None or links is None:
        rows = (await db.execute(select(WikiEntry.id, WikiEntry.title, WikiEntry.links).where(WikiEntry.user_id == user_id))).all()
        titles = {i: t for i, t, _ in rows}
        links = {i: (ln or []) for i, _, ln in rows}
    out: Dict[tuple, GraphEdge] = {}
    for src, targets in links.items():
        for dst in targets:
            if dst in titles and dst != src and src in titles:
                out[(src, dst, "link")] = GraphEdge(source=src, target=dst, kind="link", relation="링크")
    for e in (await db.execute(select(WikiEdge).where(WikiEdge.user_id == user_id))).scalars().all():
        if e.src_id in titles and e.dst_id in titles and e.src_id != e.dst_id:
            key = (e.src_id, e.dst_id, e.kind)
            if key in out:
                out[key].weight += e.weight
                if e.relation and e.relation not in out[key].relation:
                    out[key].relation = (out[key].relation + " / " + e.relation)[:60]
            else:
                out[key] = GraphEdge(source=e.src_id, target=e.dst_id, kind=e.kind, relation=e.relation, weight=e.weight)
    return list(out.values())


def _adjacency(ids, edges) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = {i: set() for i in ids}
    for e in edges:
        if e.source in adj and e.target in adj and e.source != e.target:
            adj[e.source].add(e.target)
            adj[e.target].add(e.source)
    return adj


async def build_graph(user_id: str, db: AsyncSession, types: Optional[List[str]] = None, min_weight: float = 0.0) -> GraphResponse:
    entries = (await db.execute(select(WikiEntry).where(WikiEntry.user_id == user_id).order_by(WikiEntry.updated_at.desc()).limit(MAX_NODES))).scalars().all()
    titles = {e.id: e.title for e in entries}
    edges = [e for e in await collect_edges(user_id, db, titles, {e.id: e.links or [] for e in entries}) if e.weight >= min_weight]
    ids = list(titles)
    adj = _adjacency(ids, edges)
    comm = detect_communities(ids, adj)
    type_counts = Counter((e.node_type or "source") for e in entries)
    keep = {e.id for e in entries if not types or (e.node_type or "source") in types}
    nodes = [
        GraphNode(id=e.id, title=e.title, node_type=e.node_type or "source", degree=len(adj[e.id]), community=comm[e.id],
                  summary=e.summary, auto_generated=bool(e.auto_generated), graph_status=e.graph_status or "")
        for e in entries if e.id in keep
    ]
    return GraphResponse(
        nodes=nodes,
        edges=[e for e in edges if e.source in keep and e.target in keep],
        type_counts=dict(type_counts),
        communities=len(set(comm.values())),
        pending=sum(1 for e in entries if e.graph_status == "pending"),
    )


def _ref(n: GraphNode) -> WikiLinkRef:
    return WikiLinkRef(id=n.id, title=n.title)


def make_insights(g: GraphResponse) -> GraphInsights:
    """허브(연결 많은 노드), 고립 노드, 커뮤니티 사이 다리 노드, 연결하면 좋을 후보 쌍."""
    nodes = {n.id: n for n in g.nodes}
    adj = _adjacency(list(nodes), g.edges)
    out: List[GraphInsight] = []

    hubs = [n for n in sorted(g.nodes, key=lambda n: -n.degree) if n.degree >= 3][:3]
    for n in hubs:
        out.append(GraphInsight(type="hub", message=f"'{n.title}' 는 {n.degree}개 문서와 연결된 핵심 노드입니다.", entries=[_ref(n)]))

    isolated = [n for n in g.nodes if n.degree == 0 and len(g.nodes) >= 3]
    if isolated:
        out.append(GraphInsight(type="isolated", message=f"연결이 없는 문서 {len(isolated)}개가 있습니다. 관련 문서와 연결해 보세요.", entries=[_ref(n) for n in isolated[:8]]))

    for n in g.nodes:
        if len({nodes[m].community for m in adj[n.id]} - {n.community}) >= 1 and n.degree >= 3:
            other = len({nodes[m].community for m in adj[n.id]} | {n.community})
            if other >= 3:
                out.append(GraphInsight(type="bridge", message=f"'{n.title}' 는 {other}개 주제 묶음을 이어 주는 다리 역할을 합니다.", entries=[_ref(n)]))
    out = [i for i in out if i.type != "bridge"] + [i for i in out if i.type == "bridge"][:2]

    # 이웃을 2개 이상 공유하지만 아직 연결되지 않은 쌍
    cands = []
    ids = sorted(nodes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if b in adj[a]:
                continue
            shared = adj[a] & adj[b]
            if len(shared) >= 2:
                cands.append((len(shared), a, b))
    for _, a, b in sorted(cands, reverse=True)[:3]:
        out.append(GraphInsight(type="suggestion", message=f"'{nodes[a].title}' 와 '{nodes[b].title}' 는 공통 이웃이 많은데 연결되어 있지 않습니다.", entries=[_ref(nodes[a]), _ref(nodes[b])]))
    return GraphInsights(insights=out)


async def neighbors(user_id: str, ids: List[str], db: AsyncSession) -> Dict[str, List[str]]:
    """id → 1-hop 이웃 문서 id (에이전트 검색의 그래프 확장용)."""
    if not ids:
        return {}
    want = set(ids)
    res: Dict[str, List[str]] = defaultdict(list)
    for e in await collect_edges(user_id, db):
        if e.source in want:
            res[e.source].append(e.target)
        if e.target in want:
            res[e.target].append(e.source)
    return {k: list(dict.fromkeys(v)) for k, v in res.items()}

from app.schemas.wiki import GraphEdge, GraphNode, GraphResponse
from app.services.wiki_graph import _adjacency, detect_communities, make_insights


def _g(edges, n=8):
    ids = [f"n{i}" for i in range(n)]
    es = [GraphEdge(source=a, target=b) for a, b in edges]
    adj = _adjacency(ids, es)
    comm = detect_communities(ids, adj)
    nodes = [GraphNode(id=i, title=i.upper(), node_type="entity", degree=len(adj[i]), community=comm[i]) for i in ids]
    return GraphResponse(nodes=nodes, edges=es, type_counts={}, communities=len(set(comm.values()))), comm


def test_two_clusters_and_isolated():
    g, comm = _g([("n0", "n1"), ("n1", "n2"), ("n0", "n2"), ("n3", "n4"), ("n4", "n5"), ("n3", "n5")])
    assert comm["n0"] == comm["n1"] == comm["n2"]
    assert comm["n3"] == comm["n4"] == comm["n5"]
    assert comm["n0"] != comm["n3"]
    assert comm["n6"] != comm["n0"] and comm["n6"] != comm["n7"]


def test_insights_hub_isolated_suggestion():
    g, _ = _g([("n0", "n1"), ("n0", "n2"), ("n0", "N3".lower()), ("n1", "n4"), ("n2", "n4")], n=6)
    kinds = {i.type for i in make_insights(g).insights}
    assert {"hub", "isolated", "suggestion"} <= kinds

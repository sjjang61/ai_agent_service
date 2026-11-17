"""모니터링 P0 확인: Opik 서버(REST)에서 최근 트레이스의 스팬 트리를 읽어 구조를 출력한다.

사용: PYTHONPATH=. uv run python scripts/monitoring_check.py [session-prefix] [--url http://localhost:15174] [--project ai-agent-platform]
"""
import json
import sys
import urllib.parse
import urllib.request

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = {sys.argv[i]: sys.argv[i + 1] for i in range(1, len(sys.argv) - 1) if sys.argv[i].startswith("--")}
URL = opt.get("--url", "http://localhost:15174").rstrip("/")
PROJECT = opt.get("--project", "ai-agent-platform")
PREFIX = args[0] if args else ""


def get(path: str, **params):
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{URL}/api/v1/private/{path}?{q}", timeout=20) as r:
        return json.load(r)


def short(v, n=70):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s.replace("\n", " ")[:n]


traces = get("traces", project_name=PROJECT, size=100).get("content", [])
print(f"project={PROJECT} traces={len(traces)}")
for t in sorted(traces, key=lambda x: x.get("start_time", "")):
    meta = t.get("metadata") or {}
    sess = t.get("thread_id") or meta.get("session.id") or ""
    if PREFIX and PREFIX not in json.dumps(t, ensure_ascii=False):
        continue
    spans = get("spans", project_name=PROJECT, trace_id=t["id"], size=500).get("content", [])
    print(f"\n■ trace {t['name']!r} thread={sess!r} dur={t.get('duration')}ms spans={len(spans)} usage={t.get('usage')} err={bool(t.get('error_info'))}")
    print(f"   in={short(t.get('input'))} | out={short(t.get('output'))}")
    by_parent: dict = {}
    for s in spans:
        by_parent.setdefault(s.get("parent_span_id"), []).append(s)
    ids = {s["id"] for s in spans}
    orphans = [s for s in spans if s.get("parent_span_id") and s["parent_span_id"] not in ids]

    def walk(parent, depth):
        for s in sorted(by_parent.get(parent, []), key=lambda x: x.get("start_time", "")):
            u = s.get("usage") or {}
            tok = f" tok={u.get('prompt', u.get('prompt_tokens', '?'))}/{u.get('completion', u.get('completion_tokens', '?'))}" if u else ""
            err = " ERR=" + short((s.get("error_info") or {}).get("message", ""), 50) if s.get("error_info") else ""
            print(f"   {'  ' * depth}- [{s.get('type')}] {s['name']} {s.get('duration') and int(s['duration'])}ms{tok}{err}")
            walk(s["id"], depth + 1)

    walk(None, 0)
    if orphans:
        print(f"   !! 부모를 찾지 못한 스팬 {len(orphans)}개:", [s["name"] for s in orphans][:6])

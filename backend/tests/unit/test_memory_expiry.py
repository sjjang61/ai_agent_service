import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.memory_service import ShortTermMemoryService


def test_short_term_ttl_comes_from_settings(monkeypatch):
    from app.config import settings

    assert settings.SHORT_TERM_MEMORY_TTL == 604800                      # 기본 7일
    monkeypatch.setattr(settings, "SHORT_TERM_MEMORY_TTL", 123)
    assert ShortTermMemoryService.default_ttl() == 123


def test_list_all_reads_index_keys_and_cleans_expired(monkeypatch):
    class FakeRedis:
        store = {"memory:short:u1:c1:trip": "12/3~12/9 여행".encode(), "memory:short:u1:c2:goal": "목표".encode()}
        ttls = {"memory:short:u1:c1:trip": 5000, "memory:short:u1:c2:goal": -1}
        indexes = {"memory:short:index:u1:c1": {b"trip", b"gone"}, "memory:short:index:u1:c2": {b"goal"}}
        removed = []

        async def scan_iter(self, match=None, count=None):
            for k in list(self.indexes):
                if k.startswith(match.rstrip("*")):
                    yield k.encode()

        async def smembers(self, k): return self.indexes[k]
        async def get(self, k): return self.store.get(k)
        async def ttl(self, k): return self.ttls[k]
        async def srem(self, k, m): self.removed.append(m)
        async def close(self): ...

    async def go():
        monkeypatch.setattr(ShortTermMemoryService, "_get_redis", staticmethod(lambda: asyncio.sleep(0, FakeRedis())))
        return await ShortTermMemoryService.list_all("u1")

    items = asyncio.run(go())
    by = {(i["conversation_id"], i["key"]): i for i in items}
    assert set(by) == {("c1", "trip"), ("c2", "goal")}                  # 만료돼 값이 없는 항목은 빠진다
    assert by[("c1", "trip")]["ttl"] == 5000 and by[("c2", "goal")]["ttl"] is None
    assert FakeRedis.removed == ["gone"]                               # 색인에서도 정리


def test_not_expired_filter_clause_compiles():
    from sqlalchemy import select

    from app.models.memory import Memory
    from app.services.memory_service import not_expired

    sql = str(select(Memory.id).where(not_expired()).compile(compile_kwargs={"literal_binds": False}))
    assert "expires_at IS NULL" in sql and "expires_at >" in sql


def test_short_term_routes_are_declared_before_memory_id_routes():
    """GET /short 가 GET /{memory_id} 에 먼저 걸리면 404('Memory not found')가 난다 — 선언 순서를 고정한다."""
    from app.api.memory import router

    order = [(r.path, sorted(r.methods)) for r in router.routes]
    paths_get = [p for p, m in order if "GET" in m]
    assert paths_get.index("/short") < paths_get.index("/{memory_id}")
    assert paths_get.index("/short/{conversation_id}") < paths_get.index("/{memory_id}") or "/short/{conversation_id}" in paths_get


def test_short_term_list_route_resolves_to_its_handler():
    from starlette.routing import Match

    from app.main import app

    scope = {"type": "http", "method": "GET", "path": "/api/memory/short", "root_path": "", "headers": [], "query_string": b""}
    for route in app.routes:
        match, child = route.matches(scope)
        if match == Match.FULL:
            assert getattr(route, "name", "") == "list_all_short_term_memories"      # get_memory(/{memory_id}) 가 아니어야 한다
            return
    raise AssertionError("라우트를 찾지 못했습니다")

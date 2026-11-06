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

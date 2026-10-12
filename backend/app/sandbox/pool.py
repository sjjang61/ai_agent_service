from app.config import settings
from app.sandbox.manager import SandboxManager


class SandboxPool:
    _pool: list[str] = []
    _manager = SandboxManager()

    @classmethod
    async def initialize(cls, min_size: int = None, max_size: int = None):
        # Pre-warm containers can be added here for production use
        pass

    @classmethod
    async def cleanup(cls):
        for cid in cls._pool:
            try:
                await cls._manager.destroy_sandbox(cid)
            except Exception:
                pass
        cls._pool.clear()

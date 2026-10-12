import json
from typing import Callable

import redis.asyncio as aioredis

from app.config import settings


class EventBroker:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def connect(self):
        self._redis = await aioredis.from_url(settings.REDIS_URL)

    async def publish(self, channel: str, event: dict):
        if self._redis:
            await self._redis.publish(channel, json.dumps(event))

    async def subscribe(self, channel: str, callback: Callable):
        if not self._redis:
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await callback(data)

    async def close(self):
        if self._redis:
            await self._redis.close()


event_broker = EventBroker()

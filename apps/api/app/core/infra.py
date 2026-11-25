"""Redis (caché, rate limit, tickets, pub/sub) con respaldo en memoria para desarrollo/tests."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import defaultdict
from typing import Any

from .config import settings

try:
    import redis
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    redis = None
    aioredis = None


class MemoryStore:
    def __init__(self):
        self._d: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, k):
        with self._lock:
            v = self._d.get(k)
            if not v:
                return None
            if v[0] and v[0] < time.time():
                self._d.pop(k, None)
                return None
            return v[1]

    def set(self, k, val, ex: int | None = None):
        with self._lock:
            self._d[k] = ((time.time() + ex) if ex else 0, val)

    def delete(self, *keys):
        with self._lock:
            for k in keys:
                self._d.pop(k, None)

    def incr_window(self, k, window: int) -> int:
        with self._lock:
            exp, v = self._d.get(k, (0, 0))
            if not exp or exp < time.time():
                exp, v = time.time() + window, 0
            v += 1
            self._d[k] = (exp, v)
            return v

    def delete_prefix(self, prefix: str):
        with self._lock:
            for k in [k for k in self._d if k.startswith(prefix)]:
                self._d.pop(k, None)


class Store:
    def __init__(self):
        self.r = redis.Redis.from_url(settings.redis_url, decode_responses=True) if (settings.redis_url and redis) else None
        self.mem = MemoryStore()

    def get_json(self, k):
        v = self.r.get(k) if self.r else self.mem.get(k)
        return json.loads(v) if v else None

    def set_json(self, k, val, ex: int):
        s = json.dumps(val, default=str)
        self.r.set(k, s, ex=ex) if self.r else self.mem.set(k, s, ex)

    def pop(self, k):
        if self.r:
            return self.r.getdel(k)
        v = self.mem.get(k)
        self.mem.delete(k)
        return v

    def set(self, k, v, ex):
        self.r.set(k, v, ex=ex) if self.r else self.mem.set(k, v, ex)

    def hit(self, k, window: int = 60) -> int:
        if self.r:
            p = self.r.pipeline()
            p.incr(k)
            p.expire(k, window, nx=True)
            return int(p.execute()[0])
        return self.mem.incr_window(k, window)

    def invalidate(self, prefix: str):
        if self.r:
            for k in self.r.scan_iter(f"{prefix}*", count=500):
                self.r.delete(k)
        else:
            self.mem.delete_prefix(prefix)


store = Store()


class Broker:
    """Pub/sub por organización. Redis en producción; colas asyncio en memoria en local/tests."""

    def __init__(self):
        self.use_redis = bool(settings.redis_url and aioredis)
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop):
        self._loop = loop

    async def publish(self, channel: str, message: dict):
        data = json.dumps(message, default=str)
        if self.use_redis:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            try:
                await r.publish(channel, data)
            finally:
                await r.aclose()
        else:
            for q in list(self._subs.get(channel, ())):
                q.put_nowait(data)

    async def subscribe(self, channel: str):
        if self.use_redis:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            ps = r.pubsub()
            await ps.subscribe(channel)
            try:
                while True:
                    msg = await ps.get_message(ignore_subscribe_messages=True, timeout=15)
                    yield msg["data"] if msg else None
            finally:
                await ps.unsubscribe(channel)
                await r.aclose()
        else:
            q: asyncio.Queue = asyncio.Queue()
            self._subs[channel].add(q)
            try:
                while True:
                    try:
                        yield await asyncio.wait_for(q.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield None
            finally:
                self._subs[channel].discard(q)


broker = Broker()


def get_queue():
    """Cola RQ para trabajos de entrenamiento/ETL (None si no hay Redis)."""
    if not settings.redis_url:
        return None
    from rq import Queue

    return Queue(settings.training_queue, connection=redis.Redis.from_url(settings.redis_url), default_timeout=3600)

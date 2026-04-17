import asyncio
import logging
from functools import wraps
from typing import Callable, Any, TypeVar

from aiohttp import web

from app.config import results_per_page

log = logging.getLogger(__name__)

T = TypeVar("T")


class OptimisticLock:
    def __init__(self):
        self._locks: dict = {}
        self._lock = asyncio.Lock()

    async def get_lock(self, key: str) -> asyncio.Lock:
        async with self._lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def acquire(self, key: str) -> bool:
        lock = await self.get_lock(key)
        return await lock.acquire()

    def release(self, key: str) -> None:
        if key in self._locks:
            self._locks[key].release()


class BackPressureController:
    def __init__(self, max_concurrent: int = 50):
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: int = 0
        self._waiting_tasks: int = 0
        self._total_served: int = 0

    async def __aenter__(self) -> None:
        self._waiting_tasks += 1
        await self._semaphore.acquire()
        self._waiting_tasks -= 1
        self._active_tasks += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._active_tasks -= 1
        self._total_served += 1
        self._semaphore.release()

    @property
    def active(self) -> int:
        return self._active_tasks

    @property
    def waiting(self) -> int:
        return self._waiting_tasks


class Debouncer:
    def __init__(self, delay: float = 0.3):
        self._delay = delay
        self._timers = {}
        self._lock = asyncio.Lock()

    async def debounce(self, key: str, coro_fn: Callable) -> None:
        async with self._lock:
            if key in self._timers:
                self._timers[key].cancel()

        async def run():
            async with self._lock:
                if key in self._timers:
                    del self._timers[key]
            await coro_fn()

        loop = asyncio.get_event_loop()
        loop.call_later(self._delay, lambda: asyncio.create_task(run()))

    async def cancel(self, key: str) -> None:
        async with self._lock:
            if key in self._timers:
                self._timers[key].cancel()
                del self._timers[key]

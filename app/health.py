import asyncio
import gc
import os
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional
from collections import deque

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    uptime_start: float = field(default_factory=time.time)
    request_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    active_connections: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    status_counts: Dict[int, int] = field(default_factory=dict)

    def record_request(self, duration: float, status: int) -> None:
        self.request_count += 1
        self.response_times.append(duration)
        self.status_counts[status] = self.status_counts.get(status, 0) + 1

    def record_error(self) -> None:
        self.error_count += 1

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def error_rate(self) -> float:
        total = self.request_count
        return self.error_count / total if total > 0 else 0.0

    def get_system_info(self) -> Dict:
        result = {
            "uptime_seconds": time.time() - self.uptime_start,
            "requests": self.request_count,
            "errors": self.error_count,
            "error_rate": round(self.error_rate, 4),
            "avg_response_ms": round(self.avg_response_time * 1000, 2),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "status_codes": self.status_counts,
        }

        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()
                result["memory_mb"] = round(mem_info.rss / 1024 / 1024, 2)
                result["cpu_percent"] = process.cpu_percent()
                result["threads"] = process.num_threads()
            except Exception:
                pass

        return result


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_timeout: float = 10.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_timeout = half_open_timeout
        self._failures = 0
        self._state = "closed"
        self._last_failure_time = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def is_available(self) -> bool:
        async with self._lock:
            if self._state == "closed":
                return True

            now = time.time()

            if self._state == "open":
                if now - self._last_failure_time >= self.recovery_timeout:
                    self._state = "half_open"
                    log.info("Circuit breaker entering half-open state")
                    return True
                return False

            if self._state == "half_open":
                return now - self._last_failure_time >= self.half_open_timeout

            return True

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures = 0
                log.info("Circuit breaker closed after successful call")

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()

            if self._state == "half_open":
                self._state = "open"
                log.warning("Circuit breaker opened after failed half-open call")
            elif self._failures >= self.failure_threshold:
                self._state = "open"
                log.warning(f"Circuit breaker opened after {self._failures} failures")


class ConnectionPool:
    def __init__(self, max_size: int = 10, max_idle_time: float = 300.0):
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._created: int = 0
        self._in_use: int = 0
        self._lock = asyncio.Lock()
        self._closed = False

    async def acquire(self):
        if self._closed:
            return None

        async with self._lock:
            if self._created < self.max_size:
                self._created += 1
                conn = await self._create_connection()
                if conn:
                    self._in_use += 1
                    return conn

        try:
            conn = self._pool.get_nowait()
            self._in_use += 1
            return conn
        except asyncio.QueueEmpty:
            async with self._lock:
                if self._created < self.max_size:
                    self._created += 1
                    conn = await self._create_connection()
                    if conn:
                        self._in_use += 1
                        return conn
            await asyncio.sleep(0.01)
            return await self.acquire()

    async def release(self, conn) -> None:
        if conn is None or self._closed:
            return

        async with self._lock:
            self._in_use = max(0, self._in_use - 1)

        try:
            self._pool.put_nowait(conn)
        except asyncio.QueueFull:
            async with self._lock:
                self._created = max(0, self._created - 1)

    async def _create_connection(self):
        return {"created_at": time.time()}

    async def close(self) -> None:
        self._closed = True
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except asyncio.QueueEmpty:
                break

        async with self._lock:
            self._created = 0
            self._in_use = 0


class RequestDeduplicator:
    def __init__(self, ttl: float = 5.0, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self._requests: Dict[str, float] = {}
        self._results: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        key = f"{args}:{sorted(kwargs.items())}"
        return hex(hash(key))

    async def get_or_compute(self, key: str, coro):
        now = time.time()

        async with self._lock:
            if key in self._requests:
                if key in self._results:
                    result, expiry = self._results[key]
                    if expiry > now:
                        return result
                    del self._results[key]
                elif now - self._requests[key] < self.ttl:
                    await asyncio.sleep(0.01)
                    return await self.get_or_compute(key, coro)

            self._requests[key] = now
            self._cleanup(now)

        try:
            result = await coro
            async with self._lock:
                self._results[key] = (result, now + self.ttl)
                if key in self._requests:
                    del self._requests[key]
            return result
        except Exception:
            async with self._lock:
                if key in self._requests:
                    del self._requests[key]
            raise

    def _cleanup(self, now: float) -> None:
        if len(self._requests) > self.max_size:
            old_keys = [k for k, v in self._requests.items() if now - v > self.ttl]
            for k in old_keys:
                del self._requests[k]

        if len(self._results) > self.max_size:
            self._results = {k: v for k, v in self._results.items() if v[1] > now}


class GracefulShutdown:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._shutting_down = False
        self._connections: set = set()
        self._lock = asyncio.Lock()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    async def register(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.add(connection_id)

    async def unregister(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.discard(connection_id)

    async def begin_shutdown(self) -> None:
        self._shutting_down = True
        log.warning("Graceful shutdown initiated")

        start = time.time()
        while self._connections and time.time() - start < self.timeout:
            await asyncio.sleep(0.1)

        if self._connections:
            log.warning(
                f"Shutdown timeout, {len(self._connections)} connections remaining"
            )


health_metrics = HealthMetrics()
circuit_breaker = CircuitBreaker()
request_deduplicator = RequestDeduplicator()
graceful_shutdown = GracefulShutdown()

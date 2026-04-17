import asyncio
import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union
from pathlib import Path
import pickle
import time

from .config import logo_folder

log = logging.getLogger(__name__)

T = TypeVar("T")


class CacheStats:
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def reset(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0


class LRUCache:
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._access_order: list[str] = []
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_expired(self, entry: tuple[Any, float]) -> bool:
        return time.time() - entry[1] > self._ttl

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not self._is_expired(entry):
                    self._access_order.remove(key)
                    self._access_order.append(key)
                    return entry[0]
                else:
                    del self._cache[key]
                    self._access_order.remove(key)
            return None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
            elif len(self._cache) >= self._max_size:
                oldest = self._access_order.pop(0)
                del self._cache[oldest]
                log.debug(f"Evicted cache entry: {oldest}")

            self._cache[key] = (value, time.time())
            self._access_order.append(key)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def size(self) -> int:
        return len(self._cache)


class DiskCache:
    def __init__(self, cache_dir: Path, max_age: int = 86400):
        self._cache_dir = cache_dir
        self._max_age = max_age
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        return self._cache_dir / f"{key}.cache"

    def get(self, key: str) -> Optional[bytes]:
        path = self._get_path(key)
        if not path.exists():
            return None

        if time.time() - path.stat().st_mtime > self._max_age:
            path.unlink(missing_ok=True)
            return None

        try:
            return path.read_bytes()
        except Exception as e:
            log.debug(f"Error reading cache: {e}")
            return None

    def set(self, key: str, data: bytes) -> bool:
        path = self._get_path(key)
        try:
            path.write_bytes(data)
            return True
        except Exception as e:
            log.debug(f"Error writing cache: {e}")
            return False

    def delete(self, key: str) -> bool:
        path = self._get_path(key)
        if path.exists():
            path.unlink(missing_ok=True)
            return True
        return False

    def clear(self) -> None:
        for path in self._cache_dir.glob("*.cache"):
            path.unlink(missing_ok=True)


logo_cache = DiskCache(logo_folder / "cache", max_age=86400)
thumbnail_cache = DiskCache(logo_folder / "thumbnails", max_age=43200)

message_cache = LRUCache(max_size=200, ttl=1800)

stats = CacheStats()


def cached_message(ttl: int = 300):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> T:
            key = f"{func.__name__}:{args}:{kwargs}"
            cache_key = hashlib.md5(key.encode()).hexdigest()

            cached = await message_cache.get(cache_key)
            if cached is not None:
                stats.hits += 1
                return pickle.loads(cached)

            stats.misses += 1
            result = await func(self, *args, **kwargs)

            if result is not None:
                await message_cache.set(cache_key, pickle.dumps(result))

            return result

        return wrapper

    return decorator


async def get_cached_thumbnail(key: str) -> Optional[bytes]:
    return thumbnail_cache.get(key)


async def set_cached_thumbnail(key: str, data: bytes) -> None:
    thumbnail_cache.set(key, data)


async def get_cached_logo(key: str) -> Optional[bytes]:
    return logo_cache.get(key)


async def set_cached_logo(key: str, data: bytes) -> None:
    logo_cache.set(key, data)

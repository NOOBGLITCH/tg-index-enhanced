import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Optional

from aiohttp import web

from .config import authenticated, username, password


log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 100, window: int = 60):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._max_requests = max_requests
        self._window = window
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> bool:
        async with self._lock:
            now = time.time()
            window_start = now - self._window

            self._requests[key] = [t for t in self._requests[key] if t > window_start]

            if len(self._requests[key]) >= self._max_requests:
                return False

            self._requests[key].append(now)
            return True

    async def cleanup(self) -> None:
        async with self._lock:
            now = time.time()
            for key in list(self._requests.keys()):
                self._requests[key] = [
                    t for t in self._requests[key] if t > now - self._window
                ]
                if not self._requests[key]:
                    del self._requests[key]


rate_limiter = RateLimiter(max_requests=100, window=60)


async def check_rate_limit(request: web.Request) -> Optional[web.Response]:
    if not authenticated:
        return None

    ip = request.remote or "unknown"
    user_key = hashlib.md5(f"{ip}:{request.path}".encode()).hexdigest()[:16]

    if not await rate_limiter.is_allowed(user_key):
        return web.Response(
            status=429,
            text="429: Too Many Requests. Please slow down.",
            content_type="text/plain",
            headers={"Retry-After": "60"},
        )

    return None


def require_auth(func: Callable):
    @wraps(func)
    async def wrapper(request: web.Request, *args, **kwargs):
        if not authenticated:
            return await func(request, *args, **kwargs)

        session = request.get("session")
        if session and session.get("logged_in"):
            return await func(request, *args, **kwargs)

        return web.HTTPFound("/login")

    return wrapper


def validate_input(**validators):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: web.Request, *args, **kwargs):
            data = await request.post()

            for field, validator in validators.items():
                value = data.get(field)
                if not validator(value):
                    return web.Response(
                        status=400,
                        text=f"400: Invalid {field}",
                        content_type="text/plain",
                    )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def sanitize_path(path: str) -> str:
    return "".join(c for c in path if c.isalnum() or c in "-_.")

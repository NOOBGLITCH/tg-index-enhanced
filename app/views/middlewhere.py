import time
import json
import logging
import asyncio
import hashlib
from typing import Optional, Callable, Awaitable
from collections import defaultdict
from functools import wraps

from aiohttp.web import middleware, HTTPFound, Response, Request
from aiohttp import BasicAuth, hdrs
from aiohttp_session import get_session

from ..health import health_metrics
from ..config import authenticated as is_auth_enabled, username, password

log = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def generate_request_id() -> str:
    return hashlib.sha256(
        f"{time.time()}{asyncio.get_event_loop().time()}".encode()
    ).hexdigest()[:16]


class RateLimiter:
    def __init__(self, max_requests: int = 100, window: float = 60.0):
        self._max_requests = max_requests
        self._window = window
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._enabled = is_auth_enabled

    async def is_allowed(self, key: str) -> bool:
        if not self._enabled:
            return True

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


rate_limiter = RateLimiter(max_requests=100, window=60.0)


@middleware
async def auth_middleware(request: Request, handler) -> Response:
    request_id = generate_request_id()
    request[REQUEST_ID_HEADER] = request_id
    request["request_id"] = request_id

    if not request.app.get("is_authenticated"):
        return await handler(request)

    public_paths = {"/login", "/logout", "/favicon.ico", "/otg", "/health", "/ready"}
    path = str(request.rel_url.path)

    if path in public_paths:
        return await handler(request)

    auth_result = await _check_authentication(request)

    if auth_result is True:
        return await handler(request)

    if isinstance(auth_result, Response):
        return auth_result

    login_url = request.app.router["login_page"].url_for()
    if path != "/":
        login_url = login_url.with_query(redirect_to=path)

    return HTTPFound(login_url)


async def _check_authentication(request: Request) -> Optional[bool | Response]:
    basic_auth_response = _check_basic_auth(request)
    if isinstance(basic_auth_response, Response):
        return basic_auth_response
    if basic_auth_response is True:
        return True

    session = await get_session(request)
    if session.get("logged_in"):
        session["last_at"] = time.time()
        return True

    return None


def _check_basic_auth(request: Request) -> Optional[bool | Response]:
    auth = None
    auth_header = request.headers.get(hdrs.AUTHORIZATION)

    if auth_header:
        try:
            auth = BasicAuth.decode(auth_header=auth_header)
        except ValueError:
            pass

    if not auth:
        try:
            auth = BasicAuth.from_url(request.url)
        except ValueError:
            pass

    if not auth:
        return None

    if not auth.login or not auth.password:
        return None

    if auth.login != request.app.get("username") or auth.password != request.app.get(
        "password"
    ):
        return None

    return True


@middleware
async def security_headers_middleware(request: Request, handler) -> Response:
    try:
        response = await handler(request)
    except Exception as e:
        request_id = request.get("request_id", "unknown")
        log.error(
            f"Request error: {request.method} {request.path} [{request_id}]",
            exc_info=True,
        )
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Request-ID"] = request.get("request_id", "unknown")

    return response


@middleware
async def logging_middleware(request: Request, handler) -> Response:
    start_time = time.time()
    status = 500

    try:
        response = await handler(request)
        status = response.status
        return response
    except Exception as e:
        status = 500
        health_metrics.record_error()
        raise
    finally:
        duration = time.time() - start_time
        health_metrics.record_request(duration, status)
        log.info(
            f"{request.method} {request.path} - {status} ({duration * 1000:.1f}ms)"
        )


def require_auth(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs) -> Response:
        if not request.app.get("is_authenticated"):
            return await func(request, *args, **kwargs)

        session = await get_session(request)
        if session and session.get("logged_in"):
            return await func(request, *args, **kwargs)

        return HTTPFound("/login")

    return wrapper


async def check_rate_limit(request: Request) -> Optional[Response]:
    if not request.app.get("is_authenticated"):
        return None

    ip = request.remote or "unknown"
    user_key = hashlib.md5(f"{ip}:{request.path}".encode()).hexdigest()[:16]

    if not await rate_limiter.is_allowed(user_key):
        return Response(
            status=429,
            text="429: Too Many Requests. Please slow down.",
            content_type="text/plain",
            headers={"Retry-After": "60"},
        )

    return None


def sanitize_path(path: str) -> str:
    return "".join(c for c in path if c.isalnum() or c in "-_.")


async def cors_middleware(request: Request, handler) -> Response:
    response = await handler(request)

    allowed_origin = request.app.get("allowed_origin", "*")

    response.headers["Access-Control-Allow-Origin"] = allowed_origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Max-Age"] = "3600"

    return response

import time
import logging
from typing import Optional

from aiohttp.web import middleware, HTTPFound, Response, Request
from aiohttp import BasicAuth, hdrs
from aiohttp_session import get_session


log = logging.getLogger(__name__)


@middleware
async def auth_middleware(request: Request, handler) -> Response:
    if not request.app.get("is_authenticated"):
        return await handler(request)

    public_paths = {"/login", "/logout", "/favicon.ico", "/otg", "/health"}
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
    response = await handler(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Content-Security-Policy"] = "default-src 'self'"

    return response


@middleware
async def logging_middleware(request: Request, handler):
    start_time = time.time()

    try:
        response = await handler(request)
    except Exception as e:
        log.error(f"Request error: {request.method} {request.path}", exc_info=True)
        raise

    duration = time.time() - start_time
    log.info(f"{request.method} {request.path} - {response.status} ({duration:.3f}s)")

    return response

import asyncio
import logging
import os
import signal
import sys
from typing import Callable, Awaitable

import aiohttp_jinja2
import jinja2
from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from .telegram import Client
from .routes import setup_routes
from .views import Views
from .views.middlewhere import (
    auth_middleware,
    security_headers_middleware,
    logging_middleware,
)
from .config import (
    host,
    port,
    session_string,
    api_id,
    api_hash,
    authenticated,
    username,
    password,
    SESSION_COOKIE_LIFETIME,
    SECRET_KEY,
)
from .health import health_metrics, graceful_shutdown

log = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "status": "healthy"
            if not graceful_shutdown.is_shutting_down
            else "shutting_down",
            "metrics": health_metrics.get_system_info(),
        }
    )


async def ready_check(request: web.Request) -> web.Response:
    tg_client = request.app.get("tg_client")
    if tg_client and tg_client.is_connected:
        return web.json_response({"status": "ready"})
    return web.json_response(
        {"status": "not_ready", "message": "Telegram client not connected"},
        status=503,
    )


class Indexer:
    TEMPLATES_ROOT = os.path.join(os.path.dirname(__file__), "templates")

    def __init__(self):
        middlewares: list[Callable[[web.Request, Callable], Awaitable]] = []

        if authenticated:
            middlewares.append(
                session_middleware(
                    EncryptedCookieStorage(
                        secret_key=SECRET_KEY.encode(),
                        max_age=60 * SESSION_COOKIE_LIFETIME,
                        cookie_name="TG_INDEX_SESSION",
                        secure=True,
                    )
                )
            )

        middlewares.extend(
            [
                logging_middleware,
                security_headers_middleware,
                auth_middleware,
            ]
        )

        self.server = web.Application(middlewares=middlewares)
        self.tg_client: Client = None

        self.server.on_startup.append(self.startup)
        self.server.on_cleanup.append(self.cleanup)

        self.server["is_authenticated"] = authenticated
        self.server["username"] = username
        self.server["password"] = password

    async def startup(self, server: web.Application) -> None:
        self.tg_client = Client(session_string, api_id, api_hash)
        await self.tg_client.start()
        log.info("Telegram client started successfully")

        server["tg_client"] = self.tg_client

        loader = jinja2.FileSystemLoader(str(self.TEMPLATES_ROOT))
        aiohttp_jinja2.setup(server, loader=loader)

        await setup_routes(server, Views(self.tg_client))
        log.info("Routes configured successfully")

        server.router.add_get("/health", health_check)
        server.router.add_get("/ready", ready_check)

    async def cleanup(self, server: web.Application) -> None:
        await graceful_shutdown.begin_shutdown()

        if self.tg_client:
            try:
                await self.tg_client.disconnect()
                log.info("Telegram client disconnected")
            except Exception as e:
                log.error(f"Error disconnecting Telegram client: {e}")

    def run(self) -> None:
        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.ensure_future(self._handle_shutdown(s))
                )

        web.run_app(
            self.server,
            host=host,
            port=port,
            print=lambda x: log.info(x),
            access_log=log,
        )

    async def _handle_shutdown(self, sig) -> None:
        log.info(f"Shutdown signal {sig} received")
        await graceful_shutdown.begin_shutdown()
        await self.server.cleanup()

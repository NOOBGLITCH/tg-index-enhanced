import asyncio
import logging
import pathlib
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


log = logging.getLogger(__name__)


class Indexer:
    TEMPLATES_ROOT = pathlib.Path(__file__).parent / "templates"

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

        loader = jinja2.FileSystemLoader(str(self.TEMPLATES_ROOT))
        aiohttp_jinja2.setup(server, loader=loader)

        await setup_routes(server, Views(self.tg_client))
        log.info("Routes configured successfully")

    async def cleanup(self, server: web.Application) -> None:
        if self.tg_client:
            await self.tg_client.disconnect()
            log.info("Telegram client disconnected")

    def run(self) -> None:
        web.run_app(
            self.server,
            host=host,
            port=port,
            print=lambda x: log.info(x),
            access_log=log,
        )

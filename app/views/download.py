import logging
from typing import Optional

from aiohttp import web
from telethon.tl.custom import Message

from app.util import get_file_name
from app.config import block_downloads
from .base import BaseView


log = logging.getLogger(__name__)


class Download(BaseView):
    async def download_get(self, req: web.Request) -> web.Response:
        return await self._handle_download(req, head=False)

    async def download_head(self, req: web.Request) -> web.Response:
        return await self._handle_download(req, head=True)

    async def _handle_download(
        self, req: web.Request, head: bool = False
    ) -> web.Response:
        if block_downloads:
            return web.Response(
                status=403,
                text="403: Forbidden" if not head else None,
                content_type="text/plain",
            )

        file_id = int(req.match_info["id"])
        alias_id = req.match_info["chat"]

        try:
            chat = self.chat_ids[alias_id]
            chat_id = chat.chat_id if hasattr(chat, 'chat_id') else chat.get('chat_id') if isinstance(chat, dict) else None
            if chat_id is None:
                raise KeyError("Invalid chat")
        except (KeyError, AttributeError, TypeError):
            return web.Response(
                status=404,
                text="404: Chat not found" if not head else None,
                content_type="text/plain",
            )

        message: Optional[Message] = await self._get_message(chat_id, file_id)

        if not message or not message.file:
            return web.Response(
                status=410,
                text="410: Gone. The requested resource is no longer available."
                if not head
                else None,
                content_type="text/plain",
            )

        return await self._stream_file(req, message, head)

    async def _get_message(self, chat_id: int, file_id: int) -> Optional[Message]:
        try:
            return await self.client.get_messages(entity=chat_id, ids=file_id)
        except Exception as e:
            log.debug(f"Error getting message {file_id} in {chat_id}: {e}")
            return None

    async def _stream_file(
        self, req: web.Request, message: Message, head: bool
    ) -> web.Response:
        size = message.file.size
        mime_type = message.file.mime_type
        filename_raw = get_file_name(message, quote_name=False)

        safe_filename = filename_raw.replace('"', '\\"')

        try:
            offset, limit = self._parse_range(req, size)
        except ValueError:
            return web.Response(
                status=416,
                text="416: Range Not Satisfiable" if not head else None,
                headers={"Content-Range": f"bytes */{size}"},
                content_type="text/plain",
            )

        log.info(
            f"Serving file {message.id} (chat {message.chat_id}) | "
            f"Range: {offset}-{limit} / {size}"
        )

        if head:
            return web.Response(
                status=200,
                headers=self._build_headers(
                    safe_filename, mime_type, offset, limit, size, False
                ),
            )

        body = self.client.download(message.media, size, offset, limit)

        return web.Response(
            status=206 if offset else 200,
            body=body,
            headers=self._build_headers(
                safe_filename, mime_type, offset, limit, size, True
            ),
        )

    def _parse_range(self, req: web.Request, size: int) -> tuple[int, int]:
        http_range = req.http_range
        offset = http_range.start or 0
        limit = http_range.stop or size

        if limit > size or offset < 0 or limit < offset:
            raise ValueError("Invalid range")

        return offset, limit

    def _build_headers(
        self,
        filename: str,
        mime_type: str,
        offset: int,
        limit: int,
        size: int,
        include_body: bool,
    ) -> dict:
        return {
            "Content-Type": mime_type,
            "Content-Range": f"bytes {offset}-{limit - 1}/{size}",
            "Content-Length": str(limit - offset),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }

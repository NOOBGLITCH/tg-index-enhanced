import logging
from urllib.parse import unquote

import aiohttp_jinja2
from aiohttp import web
from telethon.tl import types
from telethon.tl.custom import Message
from markupsafe import Markup

from app.util import get_file_name, get_human_size
from app.config import block_downloads
from .base import BaseView


log = logging.getLogger(__name__)

VIDEO_EXTS = frozenset(
    ("mp4", "mkv", "avi", "mov", "webm", "ts", "3gp", "m4v", "flv", "wmv")
)
AUDIO_EXTS = frozenset(("mp3", "wav", "ogg", "m4a", "flac", "aac", "wma", "aiff"))
IMAGE_EXTS = frozenset(
    ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "tiff")
)


def _get_media_type(mime_type: str, filename: str) -> str:
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    mime_lower = mime_type.lower()
    if any(m in mime_lower for m in ("video",)) or ext in VIDEO_EXTS:
        return "video"
    if any(m in mime_lower for m in ("audio",)) or ext in AUDIO_EXTS:
        return "audio"
    if any(m in mime_lower for m in ("image",)) or ext in IMAGE_EXTS:
        return "image"
    if "pdf" in mime_lower or ext == "pdf":
        return "pdf"
    return "file"


class InfoView(BaseView):
    @aiohttp_jinja2.template("info.html")
    async def info(self, req: web.Request) -> dict:
        alias_id = req.match_info.get("chat", "")
        file_id_str = req.match_info.get("id", "")

        if not alias_id or not file_id_str:
            return {"found": False, "reason": "Invalid request", "authenticated": False}

        try:
            file_id = int(file_id_str)
        except ValueError:
            return {"found": False, "reason": "Invalid file ID", "authenticated": False}

        chat = self.chat_ids.get(alias_id)
        if not chat:
            return {"found": False, "reason": "Chat not found", "authenticated": False}

        try:
            message = await self.client.get_messages(entity=chat.chat_id, ids=file_id)
        except Exception as e:
            log.error(f"Error getting message: {e}")
            message = None

        if not message:
            return {
                "found": False,
                "reason": "Message not found",
                "authenticated": False,
            }

        result = {
            "authenticated": req.app.get("is_authenticated", False),
            "found": True,
        }

        reply_btns = []
        if message.reply_markup and hasattr(message.reply_markup, "rows"):
            try:
                for row in message.reply_markup.rows:
                    for btn in row.buttons:
                        if hasattr(btn, "url") and hasattr(btn, "text"):
                            reply_btns.append({"url": btn.url, "text": btn.text})
            except Exception:
                pass

        if message.file:
            mime_type = getattr(message.file, "mime_type", "") or ""
            file_name = get_file_name(message)
            human_size = get_human_size(message.file.size)
            media_type = _get_media_type(mime_type, file_name)

            download_url = (
                "#" if block_downloads else f"/{alias_id}/{file_id}/{file_name}"
            )
            unquoted_name = unquote(file_name)

            result.update(
                {
                    "name": unquoted_name,
                    "file_id": file_id,
                    "human_size": human_size,
                    "media_type": media_type,
                    "mime_type": mime_type,
                    "caption_html": Markup.escape(message.text or "")
                    .__str__()
                    .replace("\n", "<br>")
                    if message.text
                    else "",
                    "title": unquoted_name,
                    "reply_btns": [
                        reply_btns[i : i + 3] for i in range(0, len(reply_btns), 3)
                    ],
                    "thumbnail": f"/{alias_id}/{file_id}/thumbnail",
                    "download_url": download_url,
                    "page_id": alias_id,
                    "block_downloads": block_downloads,
                }
            )

        elif message.message:
            result.update(
                {
                    "media_type": "text",
                    "text_html": Markup.escape(message.message)
                    .__str__()
                    .replace("\n", "<br>"),
                    "page_id": alias_id,
                }
            )

        else:
            result.update(
                {
                    "media_type": "unknown",
                    "page_id": alias_id,
                }
            )

        return result

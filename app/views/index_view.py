import logging
import asyncio
import hashlib
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import aiohttp_jinja2
from aiohttp import web
from telethon.tl import types

from app.config import results_per_page, block_downloads, CACHE_TTL
from app.util import get_file_name, get_human_size
from .base import BaseView


log = logging.getLogger(__name__)

LIMIT_OPTIONS = [20, 50, 100]
DEFAULT_LIMIT = results_per_page
MAX_PAGE = 1000

VIDEO_EXTS = frozenset(
    ("mp4", "mkv", "avi", "mov", "webm", "ts", "3gp", "m4v", "flv", "wmv")
)
AUDIO_EXTS = frozenset(("mp3", "wav", "ogg", "m4a", "flac", "aac", "wma", "aiff"))
IMAGE_EXTS = frozenset(
    ("jpg", "jpeg", "png", "gif", "webp", "svg", "bmp", "ico", "tiff")
)
VIDEO_MIME = frozenset(("video",))
AUDIO_MIME = frozenset(("audio",))
IMAGE_MIME = frozenset(("image",))


class IndexView(BaseView):
    def __init__(self, client=None):
        self._message_cache: Dict[str, tuple[List, float]] = {}
        self._lock = asyncio.Lock()
        self.url_len = 8
        if client:
            self.client = client

    @aiohttp_jinja2.template("index.html")
    async def index(self, req: web.Request) -> Dict[str, Any]:
        alias_id = req.match_info["chat"]

        try:
            chat = self.chat_ids[alias_id]
            chat_id = chat.chat_id if hasattr(chat, 'chat_id') else chat.get('chat_id') if isinstance(chat, dict) else None
            chat_title = chat.title if hasattr(chat, 'title') else chat.get('title') if isinstance(chat, dict) else None
            if chat_id is None or chat_title is None:
                raise KeyError("Invalid chat")
        except (KeyError, AttributeError, TypeError):
            return {
                "found": False,
                "reason": "Chat not found",
                "authenticated": req.app.get("is_authenticated", False),
            }

        page_num = max(1, min(int(req.query.get("page", "1")), MAX_PAGE))
        search_query = req.query.get("search", "").strip()

        try:
            limit_val = int(req.query.get("limit", DEFAULT_LIMIT))
            if limit_val not in LIMIT_OPTIONS:
                limit_val = DEFAULT_LIMIT
        except (ValueError, TypeError):
            limit_val = DEFAULT_LIMIT

        telethon_offset = (page_num - 1) * limit_val

        log.debug(
            f"Chat: {alias_id} | Page: {page_num} | Limit: {limit_val} | Search: {search_query}"
        )

        cache_key = f"{chat_id}:{telethon_offset}:{limit_val}:{search_query}"

        messages = await self._fetch_messages_cached(
            chat_id, limit_val, telethon_offset, search_query, cache_key
        )

        results = self._process_messages(messages, alias_id)

        prev_page, next_page = self._build_pagination(
            req, page_num, limit_val, search_query, len(messages)
        )

        return {
            "item_list": results,
            "prev_page": prev_page,
            "cur_page": page_num,
            "next_page": next_page,
            "search": search_query,
            "limit_options": LIMIT_OPTIONS,
            "current_limit": limit_val,
            "name": chat_title,
            "logo": f"/{alias_id}/logo",
            "title": f"Index of {chat_title}",
            "authenticated": req.app.get("is_authenticated", False),
            "block_downloads": block_downloads,
            "m3u_option": (
                f"{req.app.get('username', '')}:{req.app.get('password', '')}@"
                if req.app.get("is_authenticated")
                else ""
            ),
        }

    async def _fetch_messages_cached(
        self, chat_id: int, limit: int, offset: int, search: str, cache_key: str
    ) -> List[Any]:
        if not hasattr(self, '_lock') or self._lock is None:
            self._lock = asyncio.Lock()
        if not hasattr(self, '_message_cache') or self._message_cache is None:
            self._message_cache = {}
        now = asyncio.get_event_loop().time()

        async with self._lock:
            if self._message_cache and cache_key in self._message_cache:
                messages, cache_time = self._message_cache[cache_key]
                if now - cache_time < CACHE_TTL:
                    log.debug(f"Cache hit for {cache_key}")
                    return messages
                else:
                    del self._message_cache[cache_key]

        messages = await self._fetch_messages(chat_id, limit, offset, search)

        async with self._lock:
            self._message_cache[cache_key] = (messages, now)

        if len(self._message_cache) > 100:
            async with self._lock:
                expired_keys = [
                    k for k, v in self._message_cache.items() if now - v[1] > CACHE_TTL
                ]
                for k in expired_keys:
                    del self._message_cache[k]

        return messages

    async def _fetch_messages(
        self, chat_id: int, limit: int, offset: int, search: str
    ) -> List[Any]:
        try:
            kwargs: Dict[str, Any] = {
                "entity": chat_id,
                "limit": limit,
                "add_offset": offset,
            }
            if search:
                kwargs["search"] = search

            messages = await asyncio.wait_for(
                self.client.get_messages(**kwargs), timeout=10.0
            )
            return messages or []
        except asyncio.TimeoutError:
            log.error(f"Timeout fetching messages for chat {chat_id}")
            return []
        except Exception as e:
            log.error(f"Failed to fetch messages: {e}", exc_info=True)
            return []

    def _process_messages(
        self, messages: List[Any], alias_id: str
    ) -> List[Dict[str, Any]]:
        results = []
        for m in messages:
            entry = self._create_entry(m, alias_id)
            if entry:
                results.append(entry)
        return results

    def _create_entry(self, message: Any, alias_id: str) -> Optional[Dict[str, Any]]:
        if message.file and not isinstance(message.media, types.MessageMediaWebPage):
            filename = get_file_name(message, quote_name=False)
            insight = (message.text or filename)[:60]
            mime_type = message.file.mime_type or ""

            ext = ""
            if "." in filename:
                ext = filename.rsplit(".", 1)[-1].lower()

            media_type = "file"
            mime_lower = mime_type.lower()
            if any(m in mime_lower for m in VIDEO_MIME) or ext in VIDEO_EXTS:
                media_type = "video"
            elif any(m in mime_lower for m in AUDIO_MIME) or ext in AUDIO_EXTS:
                media_type = "audio"
            elif any(m in mime_lower for m in IMAGE_MIME) or ext in IMAGE_EXTS:
                media_type = "image"
            elif "pdf" in mime_lower or ext == "pdf":
                media_type = "pdf"

            return {
                "file_id": message.id,
                "media": True,
                "media_type": media_type,
                "thumbnail": f"/{alias_id}/{message.id}/thumbnail",
                "mime_type": mime_type,
                "filename": filename,
                "insight": insight,
                "human_size": get_human_size(message.file.size),
                "url": f"/{alias_id}/{message.id}/view",
                "download": f"{alias_id}/{message.id}/{quote(filename)}",
            }

        if message.message:
            return {
                "file_id": message.id,
                "media": False,
                "mime_type": "text/plain",
                "insight": (message.raw_text or "")[:100],
                "url": f"/{alias_id}/{message.id}/view",
            }

        return None

    def _build_pagination(
        self, req: web.Request, page: int, limit: int, search: str, result_count: int
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        prev_page = None
        if page > 1:
            query_params = {"page": page - 1, "limit": limit}
            if search:
                query_params["search"] = search
            prev_page = {
                "url": str(req.rel_url.update_query(**query_params)),
                "no": page - 1,
            }

        next_page = None
        if result_count == limit:
            query_params = {"page": page + 1, "limit": limit}
            if search:
                query_params["search"] = search
            next_page = {
                "url": str(req.rel_url.update_query(**query_params)),
                "no": page + 1,
            }

        return prev_page, next_page

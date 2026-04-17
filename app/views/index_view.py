import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import aiohttp_jinja2
from aiohttp import web
from telethon.tl import types

from app.config import results_per_page, block_downloads
from app.util import get_file_name, get_human_size
from .base import BaseView


log = logging.getLogger(__name__)

LIMIT_OPTIONS = [20, 50, 100]
DEFAULT_LIMIT = results_per_page
MAX_PAGE = 1000


class IndexView(BaseView):
    @aiohttp_jinja2.template("index.html")
    async def index(self, req: web.Request) -> Dict[str, Any]:
        alias_id = req.match_info["chat"]

        try:
            chat = self.chat_ids[alias_id]
        except KeyError:
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

        messages = await self._fetch_messages(
            chat.chat_id, limit_val, telethon_offset, search_query
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
            "name": chat.title,
            "logo": f"/{alias_id}/logo",
            "title": f"Index of {chat.title}",
            "authenticated": req.app.get("is_authenticated", False),
            "block_downloads": block_downloads,
            "m3u_option": (
                f"{req.app.get('username', '')}:{req.app.get('password', '')}@"
                if req.app.get("is_authenticated")
                else ""
            ),
        }

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

            messages = await self.client.get_messages(**kwargs)
            return messages or []
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

            return {
                "file_id": message.id,
                "media": True,
                "thumbnail": f"/{alias_id}/{message.id}/thumbnail",
                "mime_type": message.file.mime_type,
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
            prev_page = {
                "url": str(
                    req.rel_url.update_query(
                        page=page - 1, limit=limit, search=search if search else None
                    )
                ),
                "no": page - 1,
            }

        next_page = None
        if result_count == limit:
            next_page = {
                "url": str(
                    req.rel_url.update_query(
                        page=page + 1, limit=limit, search=search if search else None
                    )
                ),
                "no": page + 1,
            }

        return prev_page, next_page

import logging
from typing import List
from urllib.parse import quote

import aiohttp_jinja2
from aiohttp import web
from telethon.tl import types, custom

from app.config import results_per_page, block_downloads
from app.util import get_file_name, get_human_size
from .base import BaseView

log = logging.getLogger(__name__)

# Default limit options
LIMIT_OPTIONS = [20, 50, 100]

class IndexView(BaseView):
    @aiohttp_jinja2.template("index.html")
    async def index(self, req: web.Request) -> web.Response:
        alias_id = req.match_info["chat"]
        chat = self.chat_ids[alias_id]

        # 1. Parse Page Offset
        try:
            page_num = int(req.query.get("page", "1"))
            if page_num < 1:
                page_num = 1
        except (ValueError, TypeError):
            page_num = 1

        # 2. Parse Search Query
        search_query = req.query.get("search", "").strip()

        # 3. Parse and Validate Limit
        try:
            limit_val = int(req.query.get("limit", results_per_page))
            if limit_val not in LIMIT_OPTIONS:
                limit_val = results_per_page
        except (ValueError, TypeError):
            limit_val = results_per_page

        # Calculate offset for Telethon (0-based)
        # page 1 -> offset 0, page 2 -> offset limit_val
        telethon_offset = (page_num - 1) * limit_val

        log.debug(f"Chat: {alias_id} | Page: {page_num} | Limit: {limit_val} | Search: {search_query}")

        # 4. Fetch Messages
        messages: List[custom.Message] = []
        try:
            kwargs = {
                "entity": chat["chat_id"],
                "limit": limit_val,
                "add_offset": telethon_offset,
            }
            if search_query:
                kwargs["search"] = search_query

            messages = await self.client.get_messages(**kwargs) or []
        except Exception:
            log.error("Failed to get messages from Telethon", exc_info=True)

        # 5. Process Results
        results = []
        for m in messages:
            entry = None
            # Handle Files/Media
            if m.file and not isinstance(m.media, types.MessageMediaWebPage):
                filename = get_file_name(m, quote_name=False)
                insight = m.text[:60] if m.text else filename
                entry = dict(
                    file_id=m.id,
                    media=True,
                    thumbnail=f"/{alias_id}/{m.id}/thumbnail",
                    mime_type=m.file.mime_type,
                    filename=filename,
                    insight=insight,
                    human_size=get_human_size(m.file.size),
                    url=f"/{alias_id}/{m.id}/view",
                    download=f"{alias_id}/{m.id}/{quote(filename)}",
                )
            # Handle Plain Text
            elif m.message:
                entry = dict(
                    file_id=m.id,
                    media=False,
                    mime_type="text/plain",
                    insight=m.raw_text[:100],
                    url=f"/{alias_id}/{m.id}/view",
                )

            if entry:
                results.append(entry)

        # 6. Pagination Logic (Ensuring 'limit' stays in the URL)
        def build_query(target_page):
            q = {"page": target_page}
            if search_query:
                q["search"] = search_query
            # Always include limit if it's not the default, 
            # or keep it consistent to avoid UI jumps
            q["limit"] = limit_val 
            return q

        prev_page = None
        if page_num > 1:
            prev_page = {
                "url": str(req.rel_url.with_query(build_query(page_num - 1))),
                "no": page_num - 1
            }

        next_page = None
        # If we got a full page of results, assume there is a next page
        if len(messages) == limit_val:
            next_page = {
                "url": str(req.rel_url.with_query(build_query(page_num + 1))),
                "no": page_num + 1,
            }

        return {
            "item_list": results,
            "prev_page": prev_page,
            "cur_page": page_num,
            "next_page": next_page,
            "search": search_query,
            "limit_options": LIMIT_OPTIONS, # Pass this to template for the dropdown
            "current_limit": limit_val,
            "name": chat["title"],
            "logo": f"/{alias_id}/logo",
            "title": f"Index of {chat['title']}",
            "authenticated": req.app.get("is_authenticated", False),
            "block_downloads": block_downloads,
            "m3u_option": (
                f"{req.app.get('username', '')}:{req.app.get('password', '')}@"
                if req.app.get("is_authenticated") else ""
            ),
        }
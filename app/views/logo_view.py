import asyncio
import io
import logging
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from telethon.tl import types

from app.config import logo_folder
from .base import BaseView


log = logging.getLogger(__name__)

LOGO_CACHE_DIR = logo_folder / "cache"
LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_placeholder(chat_name: str, size: int = 200) -> bytes:
    color = tuple(random.randint(20, 100) for _ in range(3))
    im = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(im)

    try:
        font = ImageFont.truetype("arial.ttf", size // 5)
    except Exception:
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size // 5
            )
        except Exception:
            font = ImageFont.load_default()

    initials = (
        " ".join(word[0].upper() for word in (chat_name or "_").split() if word) or "_"
    )

    try:
        bbox = draw.textbbox((0, 0), initials, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except Exception:
        tw, th = len(initials) * 15, 30

    draw.text(((size - tw) / 2, (size - th) / 2), initials, fill="white", font=font)

    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


class LogoView(BaseView):
    async def logo(self, req: web.Request) -> web.Response:
        alias_id = req.match_info.get("chat", "")
        if not alias_id:
            return web.Response(
                status=400, text="Bad Request", content_type="text/plain"
            )

        is_big = bool(req.query.get("big"))
        cache_key = f"{alias_id}{'_big' if is_big else ''}"
        cache_file = LOGO_CACHE_DIR / f"{cache_key}.jpg"

        if cache_file.exists():
            try:
                body = cache_file.read_bytes()
                return web.Response(
                    status=200,
                    body=body,
                    headers={
                        "Content-Type": "image/jpeg",
                        "Cache-Control": "public, max-age=86400",
                        "ETag": f'"{cache_key}"',
                    },
                )
            except Exception:
                pass

        chat = self.chat_ids.get(alias_id)
        if not chat:
            return web.Response(status=404, text="Not Found", content_type="text/plain")

        body = None
        chat_name = chat.title or "_"

        try:
            photos = await self.client.get_profile_photos(chat.chat_id, limit=1)
            if photos:
                photo = photos[0]
                pos = -1 if is_big else min(len(photo.sizes) - 1, len(photo.sizes) // 2)
                size_obj = self.client._get_thumb(photo.sizes, pos)

                if isinstance(
                    size_obj, (types.PhotoCachedSize, types.PhotoStrippedSize)
                ):
                    body = bytes(self.client._download_cached_photo_size(size_obj))
                else:
                    media = types.InputPhotoFileLocation(
                        id=photo.id,
                        access_hash=photo.access_hash,
                        file_reference=photo.file_reference,
                        thumb_size=size_obj.type,
                    )
                    chunks = []
                    async for chunk in self.client.iter_download(media):
                        chunks.append(chunk)
                    body = b"".join(chunks)

                if body:
                    try:
                        img = Image.open(io.BytesIO(body))
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        img.save(cache_file, format="JPEG", quality=85, optimize=True)
                    except Exception:
                        pass
        except Exception as e:
            log.debug(f"Error getting logo for {alias_id}: {e}")

        if not body:
            body = _generate_placeholder(chat_name, 200 if is_big else 150)
            try:
                cache_file.write_bytes(body)
            except Exception:
                pass

        return web.Response(
            status=200,
            body=body,
            headers={
                "Content-Type": "image/jpeg",
                "Cache-Control": "public, max-age=86400",
                "ETag": f'"{cache_key}"',
            },
        )

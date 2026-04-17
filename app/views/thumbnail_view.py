import asyncio
import io
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Dict
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from telethon.tl import types, custom

from app.cache import LRUCache
from .base import BaseView


log = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=4)

THUMB_SIZE = 256
JPEG_QUALITY = 50
WEBP_QUALITY = 50

PRESET_PLACEHOLDERS: Dict[str, bytes] = {}

PLACEHOLDER_CONFIG = {
    "pdf": {"text": "PDF", "color": (220, 53, 69)},
    "zip": {"text": "ZIP", "color": (255, 193, 7)},
    "doc": {"text": "DOC", "color": (0, 123, 255)},
    "docx": {"text": "DOCX", "color": (0, 123, 255)},
    "xls": {"text": "XLS", "color": (40, 167, 69)},
    "xlsx": {"text": "XLSX", "color": (40, 167, 69)},
    "ppt": {"text": "PPT", "color": (253, 126, 20)},
    "pptx": {"text": "PPTX", "color": (253, 126, 20)},
    "txt": {"text": "TXT", "color": (108, 117, 125)},
    "mp3": {"text": "MP3", "color": (111, 66, 193)},
    "wav": {"text": "WAV", "color": (111, 66, 193)},
    "ogg": {"text": "OGG", "color": (111, 66, 193)},
    "m4a": {"text": "M4A", "color": (111, 66, 193)},
    "flac": {"text": "FLAC", "color": (111, 66, 193)},
    "aac": {"text": "AAC", "color": (111, 66, 193)},
    "mp4": {"text": "MP4", "color": (32, 201, 151)},
    "mkv": {"text": "MKV", "color": (32, 201, 151)},
    "avi": {"text": "AVI", "color": (32, 201, 151)},
    "mov": {"text": "MOV", "color": (32, 201, 151)},
    "webm": {"text": "WEBM", "color": (32, 201, 151)},
    "ts": {"text": "TS", "color": (32, 201, 151)},
    "3gp": {"text": "3GP", "color": (32, 201, 151)},
    "m4v": {"text": "M4V", "color": (32, 201, 151)},
    "flv": {"text": "FLV", "color": (32, 201, 151)},
    "wmv": {"text": "WMV", "color": (32, 201, 151)},
    "jpg": {"text": "JPG", "color": (255, 105, 180)},
    "jpeg": {"text": "JPG", "color": (255, 105, 180)},
    "png": {"text": "PNG", "color": (255, 105, 180)},
    "gif": {"text": "GIF", "color": (255, 105, 180)},
    "webp": {"text": "WEBP", "color": (255, 105, 180)},
    "svg": {"text": "SVG", "color": (255, 105, 180)},
    "bmp": {"text": "BMP", "color": (255, 105, 180)},
    "ico": {"text": "ICO", "color": (255, 105, 180)},
    "apk": {"text": "APK", "color": (60, 180, 60)},
    "exe": {"text": "EXE", "color": (200, 50, 50)},
    "rar": {"text": "RAR", "color": (150, 100, 200)},
    "7z": {"text": "7Z", "color": (150, 100, 200)},
    "tar": {"text": "TAR", "color": (150, 100, 200)},
    "gz": {"text": "GZ", "color": (150, 100, 200)},
    "csv": {"text": "CSV", "color": (33, 37, 41)},
    "json": {"text": "JSON", "color": (33, 37, 41)},
    "xml": {"text": "XML", "color": (33, 37, 41)},
    "html": {"text": "HTML", "color": (233, 69, 38)},
    "css": {"text": "CSS", "color": (33, 103, 246)},
    "js": {"text": "JS", "color": (240, 219, 79)},
}

CACHE_DIR = Path(os.environ.get("THUMBNAIL_CACHE_DIR", "/tmp/thumbs"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

thumb_cache = LRUCache(max_size=500, ttl=7200)


def get_file_type_info(mime_type: str, filename: str = "") -> dict:
    mime_type = mime_type.lower()
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    if "pdf" in mime_type or ext == "pdf":
        return PLACEHOLDER_CONFIG["pdf"]
    if (
        "zip" in mime_type
        or "compressed" in mime_type
        or ext in ("zip", "rar", "7z", "tar", "gz")
    ):
        return PLACEHOLDER_CONFIG["zip"]
    if "document" in mime_type or "word" in mime_type:
        return PLACEHOLDER_CONFIG["docx"] if "x" in ext else PLACEHOLDER_CONFIG["doc"]
    if "spreadsheet" in mime_type or "excel" in mime_type:
        return PLACEHOLDER_CONFIG["xlsx"] if "x" in ext else PLACEHOLDER_CONFIG["xls"]
    if "presentation" in mime_type or "powerpoint" in mime_type:
        return PLACEHOLDER_CONFIG["pptx"] if "x" in ext else PLACEHOLDER_CONFIG["ppt"]
    if "text" in mime_type or "plain" in mime_type:
        return PLACEHOLDER_CONFIG["txt"]
    if any(x in mime_type for x in ("audio", "mp3", "wav", "ogg")):
        return PLACEHOLDER_CONFIG.get(ext, PLACEHOLDER_CONFIG["mp3"])
    if "video" in mime_type:
        return PLACEHOLDER_CONFIG.get(ext, PLACEHOLDER_CONFIG["mp4"])
    if "image" in mime_type:
        return PLACEHOLDER_CONFIG.get(ext, PLACEHOLDER_CONFIG["jpg"])
    if ext in PLACEHOLDER_CONFIG:
        return PLACEHOLDER_CONFIG[ext]
    return {"text": (ext.upper() if ext else "FILE"), "color": (108, 117, 125)}


def make_placeholder_sync(size: int, file_info: dict) -> bytes:
    color = file_info["color"]
    text = file_info["text"]

    img = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(img)

    font = ImageFont.load_default()
    tw = len(text) * size // 6
    th = size // 3

    draw.text(((size - tw) / 2, (size - th) / 2), text, fill="white", font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def fit_to_square_sync(data: bytes, size: int) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail((size, size), Image.Resampling.LANCZOS)

        new_img = Image.new("RGB", (size, size), (30, 30, 30))
        x = (size - img.width) // 2
        y = (size - img.height) // 2
        new_img.paste(img, (x, y))

        buf = io.BytesIO()
        new_img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return data


async def make_placeholder(size: int, file_info: dict) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, make_placeholder_sync, size, file_info)


async def fit_to_square(data: bytes, size: int) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fit_to_square_sync, data, size)


async def preload_placeholders():
    for key, config in PLACEHOLDER_CONFIG.items():
        try:
            PRESET_PLACEHOLDERS[key] = await make_placeholder(THUMB_SIZE, config)
        except Exception:
            pass
    log.info(f"Preloaded {len(PRESET_PLACEHOLDERS)} placeholders")


class ThumbnailView(BaseView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending: Dict[str, asyncio.Task] = {}

    def _make_cache_key(self, alias_id: str, file_id: int) -> str:
        return f"{alias_id}:{file_id}"

    async def thumbnail_get(self, req: web.Request) -> web.Response:
        alias_id = req.match_info.get("chat", "")
        file_id_str = req.match_info.get("id", "")

        if not alias_id or not file_id_str:
            return web.Response(status=400, text="Bad request")

        try:
            file_id = int(file_id_str)
        except ValueError:
            return web.Response(status=400, text="Invalid ID")

        cache_key = self._make_cache_key(alias_id, file_id)
        etag = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        if_none_match = req.headers.get("If-None-Match", "")

        if etag == if_none_match:
            return web.Response(status=304)

        cached = await thumb_cache.get(cache_key)
        if cached:
            return web.Response(
                status=200,
                body=cached,
                headers={
                    "Content-Type": "image/jpeg",
                    "Cache-Control": "public, max-age=43200",
                    "ETag": f'"{etag}"',
                },
            )

        chat = self.chat_ids.get(alias_id)
        if not chat:
            return await self._generate_placeholder_response(
                PLACEHOLDER_CONFIG["txt"], etag
            )

        try:
            msg: Optional[custom.Message] = await asyncio.wait_for(
                self.client.get_messages(entity=chat.chat_id, ids=file_id), timeout=5.0
            )
        except asyncio.TimeoutError:
            log.debug(f"Timeout getting message {file_id}")
            return await self._generate_placeholder_response(
                PLACEHOLDER_CONFIG["txt"], etag
            )
        except Exception as e:
            log.debug(f"Get msg error: {e}")
            return await self._generate_placeholder_response(
                PLACEHOLDER_CONFIG["txt"], etag
            )

        if not msg or not msg.file:
            return await self._generate_placeholder_response(
                PLACEHOLDER_CONFIG["txt"], etag
            )

        mime_type = getattr(msg.file, "mime_type", "") or ""
        filename = getattr(msg.file, "name", "") or ""

        file_info = get_file_type_info(mime_type, filename)

        data = await self._extract_thumbnail(msg, file_info)
        if not data:
            data = await make_placeholder(THUMB_SIZE, file_info)

        data = await fit_to_square(data, THUMB_SIZE)

        img = Image.open(io.BytesIO(data))
        if img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        final_data = buf.getvalue()

        await thumb_cache.set(cache_key, final_data)

        cache_file = CACHE_DIR / f"{alias_id}_{file_id}.jpg"
        try:
            cache_file.write_bytes(final_data)
        except Exception:
            pass

        return web.Response(
            status=200,
            body=final_data,
            headers={
                "Content-Type": "image/jpeg",
                "Cache-Control": "public, max-age=43200",
                "ETag": f'"{etag}"',
            },
        )

    async def _extract_thumbnail(
        self, msg: custom.Message, file_info: dict
    ) -> Optional[bytes]:
        try:
            media = None
            thumbs = []

            if msg.document:
                media = msg.document
                thumbs = getattr(media, "thumbs", []) or []
            elif msg.photo:
                media = msg.photo
                thumbs = getattr(media, "sizes", []) or []

            if not thumbs:
                return None

            idx = min(len(thumbs) - 1, max(0, len(thumbs) // 2))
            thumb = self.client._get_thumb(thumbs, idx)

            if not thumb or isinstance(thumb, types.PhotoSizeEmpty):
                return None

            if isinstance(thumb, (types.PhotoCachedSize, types.PhotoStrippedSize)):
                return bytes(self.client._download_cached_photo_size(thumb))

            loc_cls = (
                types.InputDocumentFileLocation
                if msg.document
                else types.InputPhotoFileLocation
            )
            loc = loc_cls(
                id=media.id,
                access_hash=media.access_hash,
                file_reference=media.file_reference,
                thumb_size=thumb.type,
            )

            chunks = []
            async for chunk in self.client.iter_download(loc):
                chunks.append(chunk)

            return b"".join(chunks)
        except Exception as e:
            log.debug(f"Thumb extract error: {e}")
            return None

    async def _generate_placeholder_response(
        self, file_info: dict, etag: str
    ) -> web.Response:
        preset_key = next(
            (k for k, v in PLACEHOLDER_CONFIG.items() if v == file_info), None
        )
        if preset_key and preset_key in PRESET_PLACEHOLDERS:
            data = PRESET_PLACEHOLDERS[preset_key]
        else:
            data = await make_placeholder(THUMB_SIZE, file_info)

        return web.Response(
            status=200,
            body=data,
            headers={
                "Content-Type": "image/jpeg",
                "Cache-Control": "public, max-age=86400",
                "ETag": f'"{etag}"',
            },
        )

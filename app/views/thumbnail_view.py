import io
import logging
import random
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from aiohttp import web
from telethon.tl import types, custom

from .base import BaseView


log = logging.getLogger(__name__)

CACHE_DIR = Path("/tmp/thumbs")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

THUMB_SIZE = 300

FILE_TYPES = {
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
    "mp4": {"text": "MP4", "color": (32, 201, 151)},
    "mkv": {"text": "MKV", "color": (32, 201, 151)},
    "avi": {"text": "AVI", "color": (32, 201, 151)},
    "mov": {"text": "MOV", "color": (32, 201, 151)},
    "webm": {"text": "WEBM", "color": (32, 201, 151)},
    "jpg": {"text": "JPG", "color": (255, 105, 180)},
    "jpeg": {"text": "JPG", "color": (255, 105, 180)},
    "png": {"text": "PNG", "color": (255, 105, 180)},
    "gif": {"text": "GIF", "color": (255, 105, 180)},
    "webp": {"text": "WEBP", "color": (255, 105, 180)},
    "svg": {"text": "SVG", "color": (255, 105, 180)},
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


def get_file_type_info(mime_type: str, filename: str = "") -> dict:
    mime_type = mime_type.lower()

    if "pdf" in mime_type:
        return FILE_TYPES["pdf"]
    if "zip" in mime_type or "compressed" in mime_type or "archive" in mime_type:
        return FILE_TYPES["zip"]
    if "document" in mime_type or "word" in mime_type:
        if "x" in filename.lower():
            return FILE_TYPES["docx"]
        return FILE_TYPES["doc"]
    if "spreadsheet" in mime_type or "excel" in mime_type:
        if "x" in filename.lower():
            return FILE_TYPES["xlsx"]
        return FILE_TYPES["xls"]
    if "presentation" in mime_type or "powerpoint" in mime_type:
        if "x" in filename.lower():
            return FILE_TYPES["pptx"]
        return FILE_TYPES["ppt"]
    if "text" in mime_type or "plain" in mime_type:
        return FILE_TYPES["txt"]
    if (
        "audio" in mime_type
        or "mp3" in mime_type
        or "wav" in mime_type
        or "ogg" in mime_type
    ):
        if "mp3" in mime_type:
            return FILE_TYPES["mp3"]
        if "wav" in mime_type:
            return FILE_TYPES["wav"]
        return FILE_TYPES["ogg"]
    if "video" in mime_type:
        if "mp4" in mime_type:
            return FILE_TYPES["mp4"]
        if "mkv" in mime_type:
            return FILE_TYPES["mkv"]
        if "avi" in mime_type:
            return FILE_TYPES["avi"]
        if "mov" in mime_type:
            return FILE_TYPES["mov"]
        if "webm" in mime_type:
            return FILE_TYPES["webm"]
        return {"text": "VID", "color": (32, 201, 151)}
    if "image" in mime_type:
        if "png" in mime_type:
            return FILE_TYPES["png"]
        if "gif" in mime_type:
            return FILE_TYPES["gif"]
        if "webp" in mime_type:
            return FILE_TYPES["webp"]
        if "svg" in mime_type:
            return FILE_TYPES["svg"]
        return FILE_TYPES["jpg"]
    if "application" in mime_type or "octet-stream" in mime_type:
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        if ext in FILE_TYPES:
            return FILE_TYPES[ext]
        return {"text": ext.upper() or "FILE", "color": (108, 117, 125)}

    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext in FILE_TYPES:
        return FILE_TYPES[ext]

    return {"text": "FILE", "color": (108, 117, 125)}


def make_placeholder(size: int, file_info: dict) -> bytes:
    color = file_info["color"]
    text = file_info["text"]

    img = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
        for fp in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                font = ImageFont.truetype(fp, size // 4)
                break
            except:
                pass
    except:
        font = ImageFont.load_default()

    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except:
        tw, th = len(text) * size // 5, size // 3

    draw.text(((size - tw) / 2, (size - th) / 2), text, fill="white", font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return buf.getvalue()


def fit_to_square(data: bytes, size: int) -> bytes:
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
        new_img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
    except Exception:
        return data


class ThumbnailView(BaseView):
    async def thumbnail_get(self, req: web.Request) -> web.Response:
        alias_id = req.match_info.get("chat", "")
        file_id_str = req.match_info.get("id", "")

        if not alias_id or not file_id_str:
            return web.Response(status=400, text="Bad request")

        try:
            file_id = int(file_id_str)
        except ValueError:
            return web.Response(status=400, text="Invalid ID")

        cache_file = CACHE_DIR / f"{alias_id}_{file_id}.jpg"

        if cache_file.exists():
            try:
                data = cache_file.read_bytes()
                return web.Response(
                    status=200,
                    body=data,
                    headers={
                        "Content-Type": "image/jpeg",
                        "Cache-Control": "public, max-age=86400",
                    },
                )
            except Exception:
                pass

        chat = self.chat_ids.get(alias_id)
        if not chat:
            data = make_placeholder(THUMB_SIZE, FILE_TYPES["txt"])
            return web.Response(
                status=200, body=data, headers={"Content-Type": "image/jpeg"}
            )

        try:
            msg: Optional[custom.Message] = await self.client.get_messages(
                entity=chat.chat_id, ids=file_id
            )
        except Exception as e:
            log.debug(f"Get msg error: {e}")
            msg = None

        if not msg or not msg.file:
            data = make_placeholder(THUMB_SIZE, FILE_TYPES["txt"])
            return web.Response(
                status=200, body=data, headers={"Content-Type": "image/jpeg"}
            )

        mime_type = getattr(msg.file, "mime_type", "") or ""
        filename = getattr(msg.file, "name", "") or ""

        file_info = get_file_type_info(mime_type, filename)

        data = None
        thumbs = []
        media = None

        try:
            if msg.document:
                media = msg.document
                thumbs = getattr(media, "thumbs", []) or []
            elif msg.photo:
                media = msg.photo
                thumbs = getattr(media, "sizes", []) or []
        except Exception:
            pass

        if thumbs:
            try:
                idx = min(len(thumbs) - 1, max(0, len(thumbs) // 2))
                thumb = self.client._get_thumb(thumbs, idx)

                if thumb and not isinstance(thumb, types.PhotoSizeEmpty):
                    try:
                        if isinstance(
                            thumb, (types.PhotoCachedSize, types.PhotoStrippedSize)
                        ):
                            data = bytes(self.client._download_cached_photo_size(thumb))
                        else:
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
                            data = b"".join(chunks)
                    except Exception as e:
                        log.debug(f"Thumb download error: {e}")
            except Exception as e:
                log.debug(f"Thumb error: {e}")

        if not data:
            data = make_placeholder(THUMB_SIZE, file_info)

        if data:
            data = fit_to_square(data, THUMB_SIZE)
            try:
                cache_file.write_bytes(data)
            except Exception:
                pass

        return web.Response(
            status=200,
            body=data,
            headers={
                "Content-Type": "image/jpeg",
                "Cache-Control": "public, max-age=43200",
            },
        )

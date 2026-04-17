import random
from PIL import Image, ImageDraw, ImageFont

from aiohttp import web

from app.config import logo_folder
from .base import BaseView


class FaviconIconView(BaseView):
    async def faviconicon(self, req: web.Request) -> web.Response:
        favicon_path = logo_folder.joinpath("favicon.ico")
        text = "T"

        if not favicon_path.exists():
            W, H = 360, 360
            color = tuple((random.randint(0, 255) for _ in range(3)))
            im = Image.new("RGB", (W, H), color)
            draw = ImageDraw.Draw(im)

            try:
                font = ImageFont.truetype("arial.ttf", 100)
            except Exception:
                font = ImageFont.load_default()

            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except Exception:
                w, h = 100, 100

            draw.text(((W - w) / 2, (H - h) / 2), text, fill="white", font=font)
            im.save(favicon_path, format="ICO", size=(64, 64))

        with open(favicon_path, "rb") as fp:
            body = fp.read()

        return web.Response(
            status=200,
            body=body,
            headers={
                "Content-Type": "image/x-icon",
                "Cache-Control": "public, max-age=86400",
            },
        )

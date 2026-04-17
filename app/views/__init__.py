import base64
import hashlib
from typing import Dict, TYPE_CHECKING

from ..config import SHORT_URL_LEN
from ..telegram import Client
from .base import BaseView, ChatInfo
from .home_view import HomeView
from .wildcard_view import WildcardView
from .download import Download
from .index_view import IndexView
from .info_view import InfoView
from .logo_view import LogoView
from .thumbnail_view import ThumbnailView
from .login_view import LoginView
from .logout_view import LogoutView
from .faviconicon_view import FaviconIconView


class Views(
    HomeView,
    Download,
    IndexView,
    InfoView,
    LogoView,
    ThumbnailView,
    WildcardView,
    LoginView,
    LogoutView,
    FaviconIconView,
):
    def __init__(self, client: Client):
        self.client = client
        self.url_len = SHORT_URL_LEN
        self.chat_ids: Dict[str, ChatInfo] = {}

    def generate_alias_id(self, chat) -> str:
        chat_id = chat.id
        title = chat.title

        while True:
            orig_id = f"{chat_id}"
            unique_hash = hashlib.md5(orig_id.encode()).digest()
            alias_id = base64.b64encode(unique_hash, b"__").decode()[: self.url_len]

            if alias_id in self.chat_ids:
                self.url_len += 1
                continue

            if self.url_len > SHORT_URL_LEN:
                self.url_len = SHORT_URL_LEN

            self.chat_ids[alias_id] = ChatInfo(
                chat_id=chat_id,
                alias_id=alias_id,
                title=title,
            )

            return alias_id

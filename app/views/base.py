from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from ..telegram import Client


@dataclass
class ChatInfo:
    chat_id: int
    alias_id: str
    title: str


class BaseView:
    client: "Client"
    url_len: int
    chat_ids: Dict[str, ChatInfo]

import math
import logging
import asyncio
import random
import time
from functools import wraps
from typing import Callable, Optional, TypeVar

from telethon import TelegramClient, utils
from telethon.errors import (
    FloodWaitError,
)
from telethon.sessions import StringSession

T = TypeVar("T")


def with_retry(max_retries: int = 3, backoff_base: float = 1.0):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(self, *args, **kwargs)
                except FloodWaitError as e:
                    wait_time = e.attempt * backoff_base + random.uniform(0.1, 0.5)
                    self.log.warning(
                        f"Flood wait, retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = e
                except (TimeoutError, OSError, ConnectionError) as e:
                    wait_time = backoff_base * (2**attempt) + random.uniform(0.1, 0.5)
                    self.log.warning(
                        f"Temporary error, retrying in {wait_time:.1f}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    last_exception = e
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    self.log.warning(f"Error on attempt {attempt + 1}: {e}")
                    await asyncio.sleep(backoff_base)
                    last_exception = e

            raise last_exception

        return wrapper

    return decorator


class Client(TelegramClient):
    def __init__(self, session_string: str, *args, **kwargs):
        super().__init__(StringSession(session_string), *args, **kwargs)
        self.log = logging.getLogger(__name__)
        self._request_count = 0
        self._error_count = 0
        self._last_error_time = 0.0

    async def start(self, *args, **kwargs) -> "Client":
        try:
            await super().start(*args, **kwargs)
            me = await self.get_me()
            self.log.info(f"Telegram client connected (user: {me.first_name})")
            return self
        except Exception as e:
            self.log.error(f"Failed to start Telegram client: {e}")
            raise

    def increment_request(self) -> None:
        self._request_count += 1

    def increment_error(self) -> None:
        self._error_count += 1
        self._last_error_time = time.time()

    @property
    def error_rate(self) -> float:
        total = self._request_count
        return self._error_count / total if total > 0 else 0.0

    @property
    def is_healthy(self) -> bool:
        if self.error_rate > 0.5:
            return False
        if time.time() - self._last_error_time < 60:
            return False
        return True

    @with_retry(max_retries=3, backoff_base=0.5)
    async def get_messages_safe(self, entity, ids, **kwargs):
        self.increment_request()
        try:
            result = await self.get_messages(entity, ids=ids, **kwargs)
            return result
        except Exception as e:
            self.increment_error()
            raise

    @with_retry(max_retries=3, backoff_base=0.5)
    async def get_dialogs_safe(self, **kwargs):
        self.increment_request()
        try:
            result = await self.get_dialogs(**kwargs)
            return result
        except Exception as e:
            self.increment_error()
            raise

    async def download(self, file, file_size, offset, limit):
        part_size = utils.get_appropriated_part_size(file_size) * 1024

        if part_size <= 0:
            part_size = 1024 * 1024

        first_part_cut = offset % part_size
        first_part = math.floor(offset / part_size)
        last_part_cut = part_size - (limit % part_size) if limit % part_size else 0
        last_part = math.ceil(limit / part_size)
        part_count = math.ceil(file_size / part_size)
        part = first_part
        self.log.debug(
            f"""Request Details
              part_size(bytes) = {part_size},
              first_part = {first_part}, cut = {first_part_cut}(length={part_size - first_part_cut}),
              last_part = {last_part}, cut = {last_part_cut}(length={last_part_cut}),
              parts_count = {part_count}
            """
        )
        try:
            async for chunk in self.iter_download(
                file, offset=first_part * part_size, request_size=part_size
            ):
                self.log.debug(f"Part {part}/{last_part} (total {part_count}) served!")
                if part == first_part:
                    yield chunk[first_part_cut:]
                elif part == last_part:
                    if last_part_cut:
                        yield chunk[:last_part_cut]
                    break
                else:
                    yield chunk

                part += 1

            self.log.debug("serving finished")
        except (GeneratorExit, StopAsyncIteration, asyncio.CancelledError):
            self.log.debug("file serve interrupted")
            raise
        except Exception:
            self.log.debug("file serve errored", exc_info=True)

    async def iter_messages_optimized(
        self,
        entity,
        limit: int = 100,
        offset_id: int = 0,
        min_id: int = 0,
        max_id: int = 0,
        add_offset: int = 0,
        search: Optional[str] = None,
        filter: Optional[Callable] = None,
        from_user: Optional[int] = None,
        wait_time: Optional[int] = None,
        ids: Optional[list] = None,
        reverse: bool = False,
    ):
        current_offset = offset_id
        remaining = limit
        last_message_id = None

        while remaining > 0:
            take = min(remaining, 100)

            messages = await self.get_messages(
                entity,
                limit=take,
                offset_id=current_offset,
                min_id=min_id,
                max_id=max_id,
                add_offset=add_offset,
                search=search,
                filter=filter,
                from_user=from_user,
                wait_time=wait_time,
                reverse=reverse,
            )

            if not messages:
                break

            for message in messages:
                yield message
                remaining -= 1
                last_message_id = message.id

                if remaining <= 0:
                    break

            if len(messages) < take:
                break

            current_offset = messages[-1].id

        if last_message_id and remaining > 0 and not reverse:
            pass

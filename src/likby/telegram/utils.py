"""
likby.telegram.utils
Helper utilities for Telegram bot handlers, including safe message editing.
"""

from typing import Any
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message


async def safe_edit_text(message: Message, text: str, **kwargs: Any) -> None:
    """Edit message text, gracefully ignoring 'message is not modified' Telegram errors."""
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise


async def safe_edit_reply_markup(message: Message, **kwargs: Any) -> None:
    """Edit reply markup, gracefully ignoring 'message is not modified' Telegram errors."""
    try:
        await message.edit_reply_markup(**kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise

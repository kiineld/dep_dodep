"""
Central navigation helpers.

All user-facing screens are photo + caption messages.
We cache the banner file_id after the first upload so subsequent
sends use Telegram's CDN instead of re-uploading from disk.
"""
from __future__ import annotations

import logging
from typing import Optional

from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import settings

logger = logging.getLogger(__name__)

# Cached file_id after first upload — avoids re-reading disk on every send
_banner_file_id: Optional[str] = None


def _get_photo():
    """Return cached file_id or FSInputFile for first upload."""
    if _banner_file_id:
        return _banner_file_id
    return FSInputFile(settings.banner_photo)


async def send_photo_message(
    target: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    """Send a new photo+caption message (Message target)."""
    global _banner_file_id
    sent = await target.answer_photo(
        photo=_get_photo(),
        caption=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    if not _banner_file_id and sent.photo:
        _banner_file_id = sent.photo[-1].file_id
        logger.info(f"Banner file_id cached: {_banner_file_id}")
    return sent


async def edit_or_resend(
    callback: CallbackQuery,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> None:
    """
    Edit the current message caption (photo message) or, if the current
    message is a plain-text message, delete it and send a fresh photo+caption.
    This keeps the entire UI inside the same photo bubble.
    """
    global _banner_file_id
    msg = callback.message

    # Case 1: current message already has a photo — just edit caption
    if msg.photo:
        try:
            await msg.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return  # same content, not an error
            logger.debug(f"edit_caption failed: {e}")

    # Case 2: current message is plain text — delete it and send photo
    try:
        await msg.delete()
    except Exception:
        pass

    sent = await msg.answer_photo(
        photo=_get_photo(),
        caption=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    if not _banner_file_id and sent.photo:
        _banner_file_id = sent.photo[-1].file_id
        logger.info(f"Banner file_id cached: {_banner_file_id}")


async def reply_and_delete_after(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
) -> Message:
    """
    Used after text input (e.g. amount, promo code).
    Deletes the user's text message and sends a photo+caption reply.
    """
    # Delete the user's text input message silently
    try:
        await message.delete()
    except Exception:
        pass
    return await send_photo_message(message, text, reply_markup)

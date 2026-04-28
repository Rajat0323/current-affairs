"""
bot.py — Telegram message sender.

Handles all communication with the Telegram Bot API:
  - Sending text messages (with HTML formatting)
  - Splitting long messages to stay within Telegram's 4096-char limit
  - Rate-limit-friendly sending with delays
"""

import logging
import time
from typing import Optional

import telegram
from telegram.error import TelegramError, RetryAfter, NetworkError

import config

logger = logging.getLogger(__name__)

# Module-level bot instance (lazy-initialised)
_bot: Optional[telegram.Bot] = None


def get_bot() -> telegram.Bot:
    """Return a cached telegram.Bot instance."""
    global _bot
    if _bot is None:
        _bot = telegram.Bot(token=config.TELEGRAM_BOT_TOKEN)
    return _bot


def split_message(text: str, max_length: int = config.MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Split a long message into chunks that fit within Telegram's character limit.

    Tries to split on double-newlines (paragraph boundaries) to preserve
    formatting. Falls back to hard splits if necessary.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while len(text) > max_length:
        # Find the last double-newline within the limit
        split_point = text.rfind("\n\n", 0, max_length)
        if split_point == -1:
            # Fallback: split at last single newline
            split_point = text.rfind("\n", 0, max_length)
        if split_point == -1:
            # Hard split
            split_point = max_length

        chunks.append(text[:split_point].strip())
        text = text[split_point:].strip()

    if text:
        chunks.append(text)

    return chunks


async def send_message(text: str, channel_id: str = None, retries: int = 3) -> bool:
    """
    Send a formatted HTML message to the Telegram channel.

    Automatically splits messages that exceed Telegram's limit.
    Retries up to `retries` times on transient network errors.

    Args:
        text:       The HTML-formatted message text.
        channel_id: Override for config.TELEGRAM_CHANNEL_ID.
        retries:    Number of retry attempts on failure.

    Returns:
        True if all chunks were sent successfully, False otherwise.
    """
    channel = channel_id or config.TELEGRAM_CHANNEL_ID
    bot = get_bot()
    chunks = split_message(text)

    for chunk_index, chunk in enumerate(chunks):
        attempt = 0
        sent = False

        while attempt < retries and not sent:
            try:
                await bot.send_message(
                    chat_id=channel,
                    text=chunk,
                    parse_mode=config.PARSE_MODE,
                    disable_web_page_preview=False,
                )
                logger.info(
                    "Message chunk %d/%d sent to %s", chunk_index + 1, len(chunks), channel
                )
                sent = True

            except RetryAfter as e:
                # Telegram rate-limit: wait the specified seconds
                wait = e.retry_after + 1
                logger.warning("Rate limited by Telegram. Waiting %d seconds...", wait)
                time.sleep(wait)
                attempt += 1

            except NetworkError as e:
                logger.warning("Network error (attempt %d/%d): %s", attempt + 1, retries, e)
                time.sleep(3)
                attempt += 1

            except TelegramError as e:
                logger.error("Telegram API error: %s", e)
                return False

        if not sent:
            logger.error("Failed to send chunk %d after %d attempts", chunk_index + 1, retries)
            return False

        # Small delay between chunks to avoid hitting rate limits
        if chunk_index < len(chunks) - 1:
            time.sleep(1)

    return True


async def send_test_message() -> bool:
    """Send a test ping to verify bot configuration is working."""
    test_text = (
        "✅ <b>UPSC Current Affairs Bot is online!</b>\n\n"
        "The bot is configured correctly and ready to send:\n"
        "  🌅 Morning current affairs at 7:00 AM IST\n"
        "  📝 Afternoon MCQ quiz at 1:00 PM IST\n"
        "  🌙 Evening revision at 7:00 PM IST\n\n"
        "<i>Bot powered by NewsAPI + python-telegram-bot</i>"
    )
    return await send_message(test_text)

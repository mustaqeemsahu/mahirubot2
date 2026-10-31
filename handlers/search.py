# ==========================================
# MAHIRU DIRECT ANIME SEARCH
# ==========================================

import logging
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import FORCE_CHANNEL
from database.mongo import get_all_anime
from utils.direct_filter import (
    search_anime,
    available_languages,
)

logger = logging.getLogger(__name__)


# ==========================================
# COLOURED BUTTONS
# ==========================================

def colored_button(text, url=None, callback_data=None, style=None):
    """
    Support newer PTB versions with button styles.
    Older PTB versions receive ordinary buttons.
    """

    kwargs = {"text": text}

    if url is not None:
        kwargs["url"] = url

    if callback_data is not None:
        kwargs["callback_data"] = callback_data

    if style:
        try:
            return InlineKeyboardButton(
                **kwargs,
                style=style
            )
        except TypeError:
            pass

    return InlineKeyboardButton(**kwargs)


# ==========================================
# CHANNEL URL
# ==========================================

def main_channel_url():
    channel = str(FORCE_CHANNEL or "").strip()

    if channel.startswith("https://t.me/"):
        return channel

    if channel.startswith("@"):
        channel = channel[1:]

    if channel and not channel.lstrip("-").isdigit():
        return f"https://t.me/{channel}"

    return None


# ==========================================
# RESULT BUTTONS
# ==========================================

def build_buttons(anime):

    keyboard = []

    languages = available_languages(anime)

    # HINDI - GREEN
    if "hindi" in languages:
        keyboard.append([
            colored_button(
                "🇮🇳 Watch Hindi",
                url=languages["hindi"],
                style="success"
            )
        ])

    # ENGLISH - BLUE
    if "english" in languages:
        keyboard.append([
            colored_button(
                "🇬🇧 Watch English",
                url=languages["english"],
                style="primary"
            )
        ])

    # LEGACY LINK SUPPORT
    if not languages:
        old_link = anime.get("link")

        if old_link and str(old_link).strip() != "-":
            keyboard.append([
                colored_button(
                    "🎬 Watch & Download",
                    url=old_link,
                    style="success"
                )
            ])

    # MAIN CHANNEL - RED
    channel_url = main_channel_url()

    if channel_url:
        keyboard.append([
            colored_button(
                "📢 Join Our Main Channel",
                url=channel_url,
                style="danger"
            )
        ])

    return InlineKeyboardMarkup(keyboard)


# ==========================================
# SEND ANIME RESULT
# ==========================================

async def send_anime_result(message, anime):

    name = str(anime.get("name") or "Unknown Anime")

    sticker = anime.get("sticker")

    languages = available_languages(anime)

    # Telegram supports reply_markup on sendSticker. One message only.
    keyboard = build_buttons(anime)
    if sticker and str(sticker).strip() != "-":
        try:
            await message.reply_sticker(sticker=sticker, reply_markup=keyboard)
            return
        except TelegramError:
            logger.warning("Could not send search sticker for %s", name, exc_info=True)

    # Fallback for old entries with invalid/missing stickers.
    await message.reply_text(
        f"🎬 <b>{escape(name)}</b>\n👇 Select your language.",
        parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True,
    )


# ==========================================
# MULTIPLE MATCH SELECTION
# ==========================================

async def show_matches(message, matches):

    keyboard = []

    for anime in matches:

        anime_id = str(anime.get("_id", ""))

        if not anime_id:
            continue

        keyboard.append([
            colored_button(
                f"🎬 {anime.get('name', 'Unknown Anime')}",
                callback_data=f"directanime:{anime_id}",
                style="primary"
            )
        ])

    if not keyboard:
        return

    await message.reply_text(
        "🎌 <b>Multiple anime found!</b>\n\n"
        "Please select the anime you want:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================
# DIRECT SEARCH
# ==========================================

async def direct_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

   # Ignore messages while admin is adding anime.
    if context.user_data.get("mahiru_add_busy"):
        return

    if not message or not message.text:
        return

    # Ignore commands
    if message.text.startswith("/"):
        return

    # Ignore bot messages
    if update.effective_user and update.effective_user.is_bot:
        return

    query = message.text.strip()

    if not query:
        return

    # Load existing anime collection
    animes = await get_all_anime()

    # Use our new manual keyword engine
    matches = search_anime(
        query,
        animes,
        limit=10
    )

    # No matching keyword: remain silent
    if not matches:
        return

    # Single result
    if len(matches) == 1:
        await send_anime_result(
            message,
            matches[0]
        )
        return

    # Multiple results
    await show_matches(message, matches)


# ==========================================
# ANIME SELECTION CALLBACK
# ==========================================

async def direct_anime_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    if not data.startswith("directanime:"):
        return

    anime_id = data.split(":", 1)[1]

    animes = await get_all_anime()

    selected = next(
        (
            anime for anime in animes
            if str(anime.get("_id")) == anime_id
        ),
        None
    )

    if not selected:
        await query.message.reply_text(
            "❌ Anime not found. Please search again."
        )
        return

    await send_anime_result(
        query.message,
        selected
    )


# ==========================================
# OPTIONAL /SEARCH COMMAND
# ==========================================

async def improved_anime(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not context.args:
        await update.message.reply_text(
            "🔎 Usage: /search Seven Knights"
        )
        return

    query = " ".join(context.args)

    animes = await get_all_anime()

    matches = search_anime(query, animes, limit=10)

    if not matches:
        await update.message.reply_text(
            "❌ No anime found."
        )
        return

    if len(matches) == 1:
        await send_anime_result(
            update.message,
            matches[0]
        )
    else:
        await show_matches(
            update.message,
            matches
        )


# ==========================================
# LEGACY /BTN COMPATIBILITY
# ==========================================

async def button_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await improved_anime(update, context)

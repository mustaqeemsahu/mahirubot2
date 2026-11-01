"""Simple /start welcome: one photo, personal greeting and three buttons."""

from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    MAIN_CHANNEL_URL,
    REPORT_GROUP_ID,
    START_PHOTO,
    SUPPORT_GROUP_URL,
)
from database.mongo import add_user
from utils.helpers import now


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    # Register the user without preventing the welcome message if MongoDB fails.
    try:
        await add_user(user.id)
    except Exception as exc:
        print(f"[START] Could not save user: {exc}")

    # Keep existing report-group logging behavior.
    try:
        chat_type = "PRIVATE" if chat.type == "private" else "GROUP"
        await context.bot.send_message(
            chat_id=REPORT_GROUP_ID,
            text=(
                "🚀 <b>BOT STARTED</b>\n\n"
                f"📍 Type: {chat_type}\n"
                f"👤 User: {escape(user.full_name)}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🕒 Time: {escape(str(now()))}"
            ),
            parse_mode="HTML",
        )
    except Exception as exc:
        print(f"[START] Report log failed: {exc}")

    bot_username = context.bot.username
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Main Channel", url=MAIN_CHANNEL_URL)],
            [InlineKeyboardButton("💬 Support Group", url=SUPPORT_GROUP_URL)],
            [
                InlineKeyboardButton(
                    "➕ Add Me To Your Group",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                )
            ],
        ]
    )

    first_name = escape(user.first_name or "there")
    caption = (
        f'👋 <b>Hey, <a href="tg://user?id={user.id}">{first_name}</a>!</b>\n\n'
        "🎌 <b>Welcome to Anime Search Bot!</b>\n\n"
        "Search for your favourite anime by simply sending its name.\n"
        "Can't find an anime? Request it using <code>/request Anime Name</code>.\n\n"
        "✨ Add me to your group and let everyone search for anime together!\n\n"
        "<i>Choose an option below to get started.</i>"
    )

    try:
        await message.reply_photo(
            photo=START_PHOTO,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as exc:
        # Text fallback keeps /start usable if the configured image is unavailable.
        print(f"[START] Photo send failed: {exc}")
        await message.reply_text(
            text=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

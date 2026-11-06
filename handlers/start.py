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
from utils.report_logger import send_report


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
        await send_report(
            context.bot,
            text=(
                "🚀 <b>ʙᴏᴛ ꜱᴛᴀʀᴛᴇᴅ</b>\n\n"
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
            [
                InlineKeyboardButton("📖 Help", callback_data="start_help"),
                InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP_URL),
            ],
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
        f'<blockquote>👋 <b>Hey, <a href="tg://user?id={user.id}">{first_name}</a>!</b></blockquote>\n\n'
        "🎌 <b>Welcome to Anime Search Bot!</b>\n\n"
        "﻿➲ Search For Your Favourite Anime By Simply Sending Its Name.\n"
        "﻿➲ Can't Find Anime? Request It Using <code>/request</code> or Check Anime List By <code>/animelist</code> Commond\n\n"
        "<b>✨ Add Me To Your Group And Let Everyone Search & Enjoy Anime Together!</b>\n\n"
        "<blockquote><b>➪ Join Main : @Anime_Stream_Zone</b></blockquote>"
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

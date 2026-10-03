# ==============================
# SEARCH HANDLER
# ==============================

import re
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from database.mongo import get_all_anime
from utils.cooldown import check_cooldown
from utils.filters import force_sub
from config import FORCE_CHANNEL
from utils.anime_search import find_anime_matches


# ==============================
# SMALL CAPS MAPPING
# ==============================

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


# ==============================
# NORMALIZE
# ==============================

def normalize(text: str):

    text = text.lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==============================
# AUTO DELETE
# ==============================

async def auto_delete(message, sec=120):

    await asyncio.sleep(sec)

    try:
        await message.delete()
    except:
        pass


# ==============================
# BUTTON BUILDER
# ==============================

def build_buttons(anime):

    keyboard = []

    hindi = anime.get("hindi_link")
    english = anime.get("english_link")

    old_link = anime.get("link")

    if hindi and hindi != "-":
        keyboard.append([
            InlineKeyboardButton(
                "𝖶𝖺𝗍𝖼𝗁 𝖨𝗇 𝖧𝗂𝗇𝖽𝗂 𝖣𝗎𝖻",
                url=hindi,
                style="success"
            )
        ])

    if english and english != "-":
        keyboard.append([
            InlineKeyboardButton(
                "𝖶𝖺𝗍𝖼𝗁 𝖨𝗇 𝖩𝖺𝗉/𝖤𝗇𝗀𝗅𝗂𝗌𝗁",
                url=english,
                style="success"
            )
        ])

    if (
        (not hindi or hindi == "-")
        and (not english or english == "-")
        and old_link
    ):
        keyboard.append([
            InlineKeyboardButton(
                "𝗪𝗮𝘁𝗰𝗵 & 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱",
                url=old_link,
                style="success"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "𝖩𝗈𝗂𝗇 𝖬𝖺𝗂𝗇 𝖢𝗁𝖺𝗇𝗇𝖾𝗅",
            url=f"https://t.me/{FORCE_CHANNEL.replace('@', '')}",
            style="success"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# ==============================
# PARTIAL SEARCH (/search)
# ==============================

async def improved_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await force_sub(update, context):
        return

    user_id = update.effective_user.id

    if not check_cooldown(user_id, seconds=3):
        return await update.message.reply_text(
            "⏳ ᴡᴀɪᴛ 3 sᴇᴄ"
        )

    query = " ".join(context.args)

    if not query:
        return await update.message.reply_text(
            "ᴇxᴀᴍᴘʟᴇ:\n/search Naruto"
        )

    animes = await get_all_anime()

    result = find_anime_matches(query, animes, limit=5)
    matches = result.get("matches", [])

    if not matches:
        return await update.message.reply_text(
            "❌ ɴᴏ ᴀɴɪᴍᴇ ғᴏᴜɴᴅ."
        )

    text = "🎌 sᴇᴀʀᴄʜ ʀᴇsᴜʟᴛs\n\n"

    for anime in matches[:5]:
        text += f"• {anime['name']}\n"

    sent = await update.message.reply_text(text)
    asyncio.create_task(auto_delete(sent, 120))


# ==============================
# BUTTON SEARCH (/btn)
# ==============================

async def button_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await force_sub(update, context):
        return

    query = " ".join(context.args)

    if not query:
        return await update.message.reply_text(
            "ᴇxᴀᴍᴘʟᴇ:\n/btn Naruto"
        )

    animes = await get_all_anime()

    result = find_anime_matches(query, animes, limit=5)
    matches = result.get("matches", [])

    if not matches:
        return await update.message.reply_text(
            "❌ ɴᴏ ᴀɴɪᴍᴇ ғᴏᴜɴᴅ."
        )

    keyboard = []

    for anime in matches[:5]:

        keyboard.append([
            InlineKeyboardButton(
                anime["name"],
                callback_data=f"anime_{anime['name']}",
                style="primary"
            )
        ])

    sent = await update.message.reply_text(
        "🎌 sᴇʟᴇᴄᴛ ᴀɴɪᴍᴇ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    asyncio.create_task(auto_delete(sent, 120))
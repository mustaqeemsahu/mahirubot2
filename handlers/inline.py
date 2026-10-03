# ==============================
# INLINE HANDLER
# ==============================

from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedSticker, Update
from telegram.ext import ContextTypes

from database.mongo import get_all_anime
from config import FORCE_CHANNEL


# ==============================
# SMALL CAPS MAPPING
# ==============================

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


# ==============================
# INLINE QUERY
# ==============================

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.inline_query.query.lower().strip()

    if not query:
        return

    animes = await get_all_anime()

    results = []

    # 🔥 Promo
    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}", style="success")]]

    results.append(
        InlineQueryResultArticle(
            id="promo",
            title="🔥 Anime Bot",
            input_message_content=InputTextMessageContent(
                "🔥 <b>ᴀɴɪᴍᴇ ᴘʀᴏᴠɪᴅᴇʀ ʙᴏᴛ</b>\n\nsᴇᴀʀᴄʜ ᴀɴɪᴍᴇ ɪɴsᴛᴀɴᴛʟʏ!",
                parse_mode="HTML"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    )

    # 🔍 Anime Results
    for a in animes:
        if query in a["name"].lower() or any(query in k for k in a["keys"]):

            kb = [
                [InlineKeyboardButton("🎬 Watch & Download", url=a["link"], style="success")],
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL.replace('@','')}", style="success")]
            ]

            results.append(
                InlineQueryResultCachedSticker(
                    id=f"stk_{a['name']}",
                    sticker_file_id=a["sticker"],
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            )

        if len(results) >= 10:
            break

    await update.inline_query.answer(results, cache_time=1)
# ==============================
# ANIMELIST HANDLER
# ==============================

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes

from database.mongo import get_all_anime
from config import ANIME_PER_PAGE


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
# FIXED ANIMELIST THUMBNAIL
# ==============================

ANIMELIST_THUMBNAIL = "https://files.catbox.moe/dcdjk2.jpg"


# ==============================
# BUILD PAGE
# ==============================

def build_page(animes, page):

    total = len(animes)

    total_pages = max(
        1,
        (total + ANIME_PER_PAGE - 1) // ANIME_PER_PAGE
    )

    page = max(1, min(page, total_pages))

    start = (page - 1) * ANIME_PER_PAGE
    end = start + ANIME_PER_PAGE

    return animes[start:end], page, total_pages


# ==============================
# /animelist
# ==============================

async def animelist(update: Update, context: ContextTypes.DEFAULT_TYPE):

    animes = await get_all_anime()

    if not animes:
        return await update.message.reply_text(
            "❌ ɴᴏ ᴀɴɪᴍᴇ ᴀᴅᴅᴇᴅ ʏᴇᴛ."
        )

    animes = sorted(
        animes,
        key=lambda x: x["name"].lower()
    )

    page_data, page, total_pages = build_page(
        animes,
        1
    )

    text = (
        "📚 <b>ᴀɴɪᴍᴇ ᴄᴏʟʟᴇᴄᴛɪᴏɴ</b>\n\n"
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        f"📄 <b>ᴘᴀɢᴇ :</b> {page}/{total_pages}\n"
        f"🎬 <b>ᴛᴏᴛᴀʟ :</b> {len(animes)} ᴀɴɪᴍᴇ\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
    )

    start_no = (page - 1) * ANIME_PER_PAGE

    for i, anime in enumerate(
        page_data,
        start=start_no + 1
    ):

        hindi = anime.get("hindi_link", "-")
        english = anime.get("english_link", "-")
        old = anime.get("link", "-")

        text += f"<b>{i}. {anime['name']}</b>\n"
        text += "➥ "

        links = []

        # Hindi
        if hindi and hindi != "-":
            links.append(
                f"<a href='{hindi}'>𝗛𝗶𝗻𝗱𝗶 𝗗𝘂𝗯</a>"
            )

        # English
        if english and english != "-":
            links.append(
                f"<a href='{english}'>𝗝𝗮𝗽𝗲𝗻𝘀𝗲/𝗘𝗻𝗴𝗹𝗶𝘀𝗵</a>"
            )

        # Old Database Support
        if old and old != "-" and not links:
            links.append(
                f"<a href='{old}'>🎬 Watch</a>"
            )

        if links:
            text += " | ".join(links)
        else:
            text += "❌ ɴᴏ ʟɪɴᴋ ᴀᴠᴀɪʟᴀʙʟᴇ"

        text += "\n\n"

    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if page < total_pages else total_pages

    keyboard = []

    if total_pages > 1:

        keyboard.append([
            InlineKeyboardButton(
                "⏪ Previous",
                callback_data=f"alist_{prev_page}",
                style="primary"
            ),
            InlineKeyboardButton(
                f"📄 {page}/{total_pages}",
                callback_data="ignore",
                style="primary"
            ),
            InlineKeyboardButton(
                "Next ⏩",
                callback_data=f"alist_{next_page}",
                style="primary"
            )
        ])

    markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # ==========================================
    # SEND WITH FIXED SPOILER THUMBNAIL
    # ==========================================

    try:
        await update.message.reply_photo(
            photo=ANIMELIST_THUMBNAIL,
            caption=text,
            parse_mode="HTML",
            reply_markup=markup,
            has_spoiler=True,
        )
    except Exception as e:
        print(f"[ANIMELIST] Thumbnail send failed: {e}")

        # Fallback to text-only list
        await update.message.reply_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
# ==============================
# ANIME HANDLER
# ==============================

import re
import asyncio

from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import FORCE_CHANNEL, REPORT_GROUP_ID
from database.mongo import (
    add_anime_db,
    delete_anime_db,
    get_all_anime,
)
from utils.filters import force_sub, check_bot_status
from utils.sudo import require_sudo
from utils.anime_search import find_anime_matches
from utils.anilist import find_best_match as anilist_find_best_match


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

def normalize(text: str) -> str:
    return re.sub(r"[-_]", " ", text.lower()).strip()


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
# ADD ANIME
# ==============================

async def add_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    text = update.message.text.replace("/add", "", 1).strip()

    parts = [p.strip() for p in text.split("|")]

    if len(parts) != 5:
        return await update.message.reply_text(
            "❌ <b>ꜰᴏʀᴍᴀᴛ:</b>\n\n"
            "<code>/add Anime Name | keyword1, keyword2 | STICKER_ID | HINDI_LINK_OR_- | ENGLISH_LINK_OR_-</code>\n\n"
            "<b>ᴇxᴀᴍᴘʟᴇs:</b>\n\n"
            "<code>/add Solo Leveling | solo leveling, sl | STICKER_ID | https://t.me/hindi | https://t.me/english</code>\n\n"
            "<code>/add Naruto | naruto | STICKER_ID | https://t.me/hindi | -</code>\n\n"
            "<code>/add One Piece | one piece | STICKER_ID | - | https://t.me/english</code>",
            parse_mode="HTML"
        )

    name, keywords, sticker, hindi_link, english_link = parts

    keys = [
        k.strip().lower()
        for k in keywords.split(",")
        if k.strip()
    ]

    if hindi_link == "-":
        hindi_link = None

    if english_link == "-":
        english_link = None

    await add_anime_db(
        name=name,
        keys=keys,
        sticker=sticker,
        hindi_link=hindi_link,
        english_link=english_link
    )

    msg = (
        f"✅ <b>ᴀɴɪᴍᴇ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
        f"🎬 <b>ɴᴀᴍᴇ:</b> <code>{name}</code>\n"
        f"🔑 <b>ᴋᴇʏᴡᴏʀᴅs:</b> <code>{', '.join(keys)}</code>\n"
        f"🇮🇳 <b>ʜɪɴᴅɪ:</b> {'✅ ᴀᴅᴅᴇᴅ' if hindi_link else '❌ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ'}\n"
        f"🇺🇸 <b>ᴇɴɢʟɪsʜ:</b> {'✅ ᴀᴅᴅᴇᴅ' if english_link else '❌ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ'}"
    )

    await update.message.reply_text(
        msg,
        parse_mode="HTML"
    )

# ==============================
# DELETE ANIME
# ==============================

async def del_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    name = update.message.text.replace("/del", "", 1).strip()

    if not name:
        return await update.message.reply_text(
            "ᴜsᴀɢᴇ:\n/del Anime Name"
        )

    deleted = await delete_anime_db(name)

    if deleted:
        await update.message.reply_text(
            f"✅ ᴅᴇʟᴇᴛᴇᴅ: {name}"
        )
    else:
        await update.message.reply_text(
            "❌ ᴀɴɪᴍᴇ ɴᴏᴛ ғᴏᴜɴᴅ."
        )


# ==============================
# EXACT SEARCH (/anime)
# ==============================

async def anime_search(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # FORCE SUB
    if not await force_sub(update, context):
        return

    # BOT STATUS
    if not await check_bot_status(update):
        return

    # QUERY
    raw_query = " ".join(context.args)

    if not raw_query:
        return await update.message.reply_text(
            "❌ ᴇxᴀᴍᴘʟᴇ:\n/anime Naruto"
        )

    query = normalize(raw_query)

    # DATABASE — MAHIRU FIRST (fuzzy-capable)
    anime_list = await get_all_anime()

    result = find_anime_matches(raw_query, anime_list, limit=5)
    matches = result.get("matches", [])

    # ---- SEARCH LOG ----
    try:
        await context.bot.send_message(
            chat_id=REPORT_GROUP_ID,
            text=(
                f"🔍 <b>ᴀɴɪᴍᴇ sᴇᴀʀᴄʜ</b>\n\n"
                f"👤 ᴜsᴇʀ: {update.effective_user.first_name}\n"
                f"🆔 ɪᴅ: <code>{update.effective_user.id}</code>\n"
                f"🔎 ǫᴜᴇʀʏ: <code>{query}</code>"
            ),
            parse_mode="HTML"
        )
    except:
        pass

    # ==============================
    # NO MAHIRU RESULT → ANILIST FALLBACK
    # ==============================

    if not matches:

        try:
            anilist_result = await anilist_find_best_match(raw_query)
        except Exception:
            anilist_result = None

        if not anilist_result:

            msg = await update.message.reply_text(
                "❌ ɴᴏ ᴀɴɪᴍᴇ ғᴏᴜɴᴅ."
            )

            asyncio.create_task(auto_delete(msg, 120))
            return

        # ---- ANILIST FOUND → information card ----
        title = escape(str(anilist_result.get("title") or "Unknown"))
        title_english = escape(str(anilist_result.get("title_english") or "Not available"))
        synopsis = escape(str(anilist_result.get("synopsis") or "")).strip()
        aired_from = escape(str(anilist_result.get("aired_from") or "Not available"))
        anime_type = escape(str(anilist_result.get("type") or "Not available"))
        status = escape(str(anilist_result.get("status") or "Not available"))
        anilist_url = anilist_result.get("url") or ""

        genres_list = anilist_result.get("genres") or []
        if isinstance(genres_list, list) and genres_list:
            genres = escape(", ".join(str(g) for g in genres_list))
        else:
            genres = "Not available"

        studios_list = anilist_result.get("studios") or []
        if isinstance(studios_list, list) and studios_list:
            studios = escape(", ".join(str(s) for s in studios_list))
        else:
            studios = "Not available"

        # AniList score is 0-100
        score = anilist_result.get("score", 0) or 0
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0

        popularity = anilist_result.get("popularity", 0) or 0
        try:
            popularity = int(popularity)
        except (TypeError, ValueError):
            popularity = 0

        favourites = anilist_result.get("favourites", 0) or 0
        try:
            favourites = int(favourites)
        except (TypeError, ValueError):
            favourites = 0

        episodes = anilist_result.get("episodes", 0) or 0
        try:
            episodes = int(episodes)
        except (TypeError, ValueError):
            episodes = 0

        if not synopsis:
            synopsis = "Not available"

        # Truncate synopsis to keep caption under Telegram's 1024-char limit
        if len(synopsis) > 400:
            synopsis = synopsis[:397] + "..."

        caption = (
            f"🎬 <b>ᴛɪᴛʟᴇ:</b> <b>{title}</b>\n\n"
            f"📝 <b>ᴇɴɢʟɪsʜ ᴛɪᴛʟᴇ:</b>\n"
            f"<code>{title_english}</code>\n\n"
            f"📖 <b>sʏɴᴏᴘsɪs:</b>\n"
            f"<i>{synopsis}</i>\n\n"
            f"📺 <b>ᴛʏᴘᴇ:</b> {anime_type}\n"
            f"📅 <b>ᴀɪʀᴇᴅ ғʀᴏᴍ:</b> {aired_from}\n"
            f"🎞️ <b>ᴇᴘɪsᴏᴅᴇs:</b> {episodes}\n"
            f"📡 <b>sᴛᴀᴛᴜs:</b> {status}\n\n"
            f"🎭 <b>ɢᴇɴʀᴇs:</b>\n"
            f"{genres}\n\n"
            f"🏢 <b>sᴛᴜᴅɪᴏs:</b>\n"
            f"{studios}\n\n"
            f"⭐ <b>sᴄᴏʀᴇ:</b> {score:.0f}/100\n"
            f"👥 <b>ᴘᴏᴘᴜʟᴀʀɪᴛʏ:</b> #{popularity}\n"
            f"❤️ <b>ғᴀᴠᴏᴜʀɪᴛᴇs:</b> {favourites:,}\n\n"
            "💬 <blockquote>"
            "⚠️ ᴛʜɪs ᴀɴɪᴍᴇ ɪs ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴ ᴍᴀʜɪʀᴜ ʏᴇᴛ.\n\n"
            "💡 ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛʜɪs ᴀɴɪᴍᴇ, sᴜʙᴍɪᴛ ᴀ ʀᴇǫᴜᴇsᴛ ᴜsɪɴɢ:\n"
            "<code>/request Anime Name</code>\n\n"
            "ᴏᴡɴᴇʀ ᴡɪʟʟ ᴄʜᴇᴄᴋ ᴛʜᴇ ʀᴇǫᴜᴇsᴛ ᴀɴᴅ ᴍᴀʏ ᴀᴅᴅ ɪᴛ."
            "</blockquote>"
        )

        # Add AniList page link if available
        if anilist_url:
            caption += f"\n\n🔗 <a href='{anilist_url}'>ᴠɪᴇᴡ ᴏɴ ᴀɴɪʟɪsᴛ</a>"

        image_url = anilist_result.get("image_url")

        if image_url:
            try:
                sent = await update.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    parse_mode="HTML",
                )
                asyncio.create_task(auto_delete(sent, 120))
            except Exception as e:
                print(f"[ANIME] Poster send failed: {e}")
                # Fallback: text with AniList preview enabled
                sent = await update.message.reply_text(
                    caption,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                asyncio.create_task(auto_delete(sent, 120))
        else:
            sent = await update.message.reply_text(
                caption,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            asyncio.create_task(auto_delete(sent, 120))

        return

    # ==============================
    # SINGLE MAHIRU RESULT
    # ==============================

    if len(matches) == 1:

        a = matches[0]

        old_link = a.get("link")

        keyboard = []

        hindi = a.get("hindi_link")
        english = a.get("english_link")

        if hindi and hindi != "-":
            keyboard.append([
                InlineKeyboardButton(
                    "🎬 Watch & Download",
                    url=hindi,
                    style="success"
                )
            ])
        elif english and english != "-":
            keyboard.append([
                InlineKeyboardButton(
                    "🎬 Watch & Download",
                    url=english,
                    style="success"
                )
            ])
        elif old_link:
            keyboard.append([
                InlineKeyboardButton(
                    "🎬 Watch & Download",
                    url=old_link,
                    style="success"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "📢 Join Main Channel",
                url=f"https://t.me/{FORCE_CHANNEL.replace('@', '')}",
                style="success"
            )
        ])

        sent = await update.message.reply_sticker(
            sticker=a["sticker"],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        asyncio.create_task(auto_delete(sent, 120))
        return

    # ==============================
    # MULTIPLE MAHIRU RESULTS
    # ==============================

    text = (
        f"🔎 <b>ᴍᴜʟᴛɪᴘʟᴇ ᴀɴɪᴍᴇ ғᴏᴜɴᴅ</b>\n"
        f"ǫᴜᴇʀʏ: <code>{query}</code>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                a["name"],
                callback_data=f"anime_{a['name']}",
                style="primary"
            )
        ]
        for a in matches
    ]

    sent = await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

    asyncio.create_task(auto_delete(sent, 120))
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from html import escape

from config import REPORT_GROUP_ID
from database.mongo import (
    create_request,
    request_exists,
)
from utils.tmdb import find_best_match


# ==========================
# Conversation States
# ==========================

ANIME = 1
LANGUAGE = 2
DUB = 3
SEASON = 4
EXTRA = 5


# ==========================
# TMDB INFO CARD HELPER
# ==========================

async def _send_tmdb_info(message, tmdb_result: dict) -> None:
    """
    Send a compact TMDB metadata card before Question 2.

    Never raises. Any failure is silently ignored so the request flow
    continues normally.
    """
    if not tmdb_result:
        return

    try:
        title = escape(str(tmdb_result.get("title") or "Unknown"))
        original_title = escape(str(tmdb_result.get("original_title") or "Not available"))
        overview = escape(str(tmdb_result.get("overview") or "")).strip()
        first_air_date = escape(str(tmdb_result.get("first_air_date") or "Not available"))

        genres_list = tmdb_result.get("genres") or []
        if isinstance(genres_list, list) and genres_list:
            genres = escape(", ".join(str(g) for g in genres_list))
        else:
            genres = "Not available"

        rating = tmdb_result.get("rating", 0) or 0
        try:
            rating = float(rating)
        except (TypeError, ValueError):
            rating = 0.0

        vote_count = tmdb_result.get("vote_count", 0) or 0
        try:
            vote_count = int(vote_count)
        except (TypeError, ValueError):
            vote_count = 0

        if not overview:
            overview = "Not available"

        caption = (
            "🎬 <b>ᴛᴍᴅʙ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>\n\n"
            f"📌 <b>ᴛɪᴛʟᴇ:</b> <b>{title}</b>\n"
            f"🇯🇵 <b>ᴏʀɪɢɪɴᴀʟ:</b> <code>{original_title}</code>\n\n"
            f"📅 <b>ꜰɪʀsᴛ ᴀɪʀ ᴅᴀᴛᴇ:</b> {first_air_date}\n\n"
            f"⭐ <b>ʀᴀᴛɪɴɢ:</b> {rating:.1f}/10\n"
            f"👥 <b>ᴠᴏᴛᴇs:</b> {vote_count:,}\n\n"
            f"🎭 <b>ɢᴇɴʀᴇs:</b> {genres}\n\n"
            f"📖 <i>{overview}</i>"
        )

        poster_url = tmdb_result.get("poster_url")

        if poster_url:
            try:
                await message.reply_photo(
                    photo=poster_url,
                    caption=caption,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass

        # Fallback: text only
        await message.reply_text(
            caption,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except Exception:
        # TMDB info is purely cosmetic — never let it break the request.
        return


# ==========================
# /request
# ==========================

async def request_start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        "🎬 **ᴀɴɪᴍᴇ ʀᴇǫᴜᴇsᴛ sʏsᴛᴇᴍ**\n\n"
        "ɪ'ʟʟ ᴀsᴋ ʏᴏᴜ ᴀ ғᴇᴡ ǫᴜᴇsᴛɪᴏɴs.\n"
        "ʏᴏᴜ ᴄᴀɴ ᴄᴀɴᴄᴇʟ ᴀɴʏᴛɪᴍᴇ ᴜsɪɴɢ /cancel.\n\n"
        "📺 ǫᴜᴇsᴛɪᴏɴ 1/5\n\n"
        "sᴇɴᴅ ᴛʜᴇ ᴀɴɪᴍᴇ ɴᴀᴍᴇ:",
        parse_mode="Markdown",
    )

    return ANIME


# ==========================
# Cancel Request
# ==========================

async def cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ ʀᴇǫᴜᴇsᴛ ᴄᴀɴᴄᴇʟʟᴇᴅ."
    )

    return ConversationHandler.END


# ==========================
# Skip Extra
# ==========================

async def skip_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["extra"] = "None"

    return await finish_request(update, context)


# ==========================
# Language Keyboard
# ==========================

def language_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🇮🇳 Hindi",
                    callback_data="lang_Hindi",
                    style="primary",
                ),
                InlineKeyboardButton(
                    "🇺🇸 English",
                    callback_data="lang_English",
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🇮🇳 Tamil",
                    callback_data="lang_Tamil",
                    style="primary",
                ),
                InlineKeyboardButton(
                    "🇮🇳 Telugu",
                    callback_data="lang_Telugu",
                    style="primary",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🇮🇳 Kannada",
                    callback_data="lang_Kannada",
                    style="primary",
                ),
                InlineKeyboardButton(
                    "➕ Other",
                    callback_data="lang_Other",
                    style="primary",
                ),
            ],
        ]
    )


# ==========================
# Dub Keyboard
# ==========================

def dub_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Official Dub",
                    callback_data="dub_Official",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎧 FanDub",
                    callback_data="dub_FanDub",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    "📺 Subbed",
                    callback_data="dub_Subbed",
                    style="primary",
                )
            ],
        ]
    )


# ==========================
# Anime Name
# ==========================

async def anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    anime = update.message.text.strip()

    if len(anime) < 2:
        await update.message.reply_text(
            "❌ ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ᴀɴɪᴍᴇ ɴᴀᴍᴇ."
        )
        return ANIME

    context.user_data["anime"] = anime

    # Duplicate request check — must run BEFORE TMDB lookup
    exists = await request_exists(
        user_id=update.effective_user.id,
        anime=anime,
        language=""
    )

    if exists:
        await update.message.reply_text(
            "⚠️ ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀ ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇsᴛ ғᴏʀ ᴛʜɪs ᴀɴɪᴍᴇ."
        )
        return ConversationHandler.END

    # ---- TMDB lookup (safe, best-effort, optional) ----
    try:
        tmdb_result = await find_best_match(anime)
    except Exception:
        tmdb_result = None

    if tmdb_result:
        # Persist only useful metadata for later (admin report / future use)
        context.user_data["tmdb_id"] = tmdb_result.get("tmdb_id")
        context.user_data["tmdb_title"] = tmdb_result.get("title")
        context.user_data["tmdb_original_title"] = tmdb_result.get("original_title")
        context.user_data["tmdb_overview"] = tmdb_result.get("overview")
        context.user_data["tmdb_poster_url"] = tmdb_result.get("poster_url")
        context.user_data["tmdb_backdrop_url"] = tmdb_result.get("backdrop_url")
        context.user_data["tmdb_first_air_date"] = tmdb_result.get("first_air_date")
        context.user_data["tmdb_genres"] = tmdb_result.get("genres", [])
        context.user_data["tmdb_rating"] = tmdb_result.get("rating")
        context.user_data["tmdb_vote_count"] = tmdb_result.get("vote_count")
        context.user_data["tmdb_popularity"] = tmdb_result.get("popularity")

        # Send info card — never raises to this handler
        await _send_tmdb_info(update.message, tmdb_result)

    # ---- Continue normal request flow ----
    await update.message.reply_text(
        "🌐 ǫᴜᴇsᴛɪᴏɴ 2/5\n\n"
        "sᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ:",
        reply_markup=language_keyboard()
    )

    return LANGUAGE


# ==========================
# Language Callback
# ==========================

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not query.data.startswith("lang_"):
        return LANGUAGE

    language = query.data.replace("lang_", "")

    context.user_data["language"] = language

    await query.edit_message_text(
        f"✅ ʟᴀɴɢᴜᴀɢᴇ: {language}"
    )

    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text="🎙️ ǫᴜᴇsᴛɪᴏɴ 3/5\n\nsᴇʟᴇᴄᴛ ᴅᴜʙ ᴛʏᴘᴇ:",
        reply_markup=dub_keyboard()
    )

    return DUB


# ==========================
# Dub Callback
# ==========================

async def dub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not query.data.startswith("dub_"):
        return DUB

    dub = query.data.replace("dub_", "")

    context.user_data["dub"] = dub

    await query.edit_message_text(
        f"✅ ᴅᴜʙ: {dub}"
    )

    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=(
            "🎞️ ǫᴜᴇsᴛɪᴏɴ 4/5\n\n"
            "sᴇɴᴅ sᴇᴀsᴏɴ ᴏʀ ᴍᴏᴠɪᴇ.\n\n"
            "ᴇxᴀᴍᴘʟᴇ:\n"
            "sᴇᴀsᴏɴ 1\n"
            "ᴍᴏᴠɪᴇ\n\n"
            "ʏᴏᴜ ᴄᴀɴ ᴀʟsᴏ sᴇɴᴅ /skip"
        )
    )

    return SEASON


# ==========================
# Season
# ==========================

async def season(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["season"] = update.message.text.strip()

    await update.message.reply_text(
        "📝 ǫᴜᴇsᴛɪᴏɴ 5/5\n\n"
        "sᴇɴᴅ ᴀɴʏ ᴇxᴛʀᴀ ᴅᴇᴛᴀɪʟs.\n\n"
        "ᴏʀ ᴜsᴇ /skip ɪғ ɴᴏɴᴇ."
    )

    return EXTRA


# ==========================
# Skip Season
# ==========================

async def skip_season(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["season"] = "Not Specified"

    await update.message.reply_text(
        "📝 ǫᴜᴇsᴛɪᴏɴ 5/5\n\n"
        "sᴇɴᴅ ᴀɴʏ ᴇxᴛʀᴀ ᴅᴇᴛᴀɪʟs.\n\n"
        "ᴏʀ ᴜsᴇ /skip ɪғ ɴᴏɴᴇ."
    )

    return EXTRA


# ==========================
# Extra Details
# ==========================

async def extra(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["extra"] = update.message.text.strip()

    return await finish_request(update, context)


# ==========================
# Finish Request
# ==========================

async def finish_request(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    anime = context.user_data["anime"]
    language = context.user_data["language"]
    dub = context.user_data["dub"]
    season = context.user_data["season"]
    extra = context.user_data["extra"]

    # Save to MongoDB
    req_id = await create_request(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        anime=anime,
        language=language,
        dub=dub,
        season=season,
        extra=extra,
    )

    # ---- Optional TMDB metadata block for admin report ----
    tmdb_block = ""
    tmdb_id = context.user_data.get("tmdb_id")
    tmdb_title = context.user_data.get("tmdb_title")

    if tmdb_id and tmdb_title:
        try:
            safe_title = escape(str(tmdb_title))
            safe_genres = context.user_data.get("tmdb_genres") or []
            if isinstance(safe_genres, list) and safe_genres:
                safe_genres_str = escape(", ".join(str(g) for g in safe_genres))
            else:
                safe_genres_str = "Not available"

            safe_rating = context.user_data.get("tmdb_rating", 0) or 0
            try:
                safe_rating = float(safe_rating)
            except (TypeError, ValueError):
                safe_rating = 0.0

            tmdb_block = (
                "\n🎬 <b>ᴛᴍᴅʙ ᴍᴀᴛᴄʜ</b>\n"
                f"🆔 <code>{tmdb_id}</code>\n"
                f"ᴛɪᴛʟᴇ: {safe_title}\n"
                f"ʀᴀᴛɪɴɢ: {safe_rating:.1f}\n"
                f"ɢᴇɴʀᴇs: {safe_genres_str}\n"
            )
        except Exception:
            tmdb_block = ""

    text = (
        "📥 <b>ɴᴇᴡ ᴀɴɪᴍᴇ ʀᴇǫᴜᴇsᴛ</b>\n\n"
        f"🆔 <b>{req_id}</b>\n\n"
        f"👤 <b>{user.full_name}</b>\n"
        f"🆔 <code>{user.id}</code>\n"
        f"🔗 @{user.username if user.username else 'No Username'}\n\n"

        f"📺 <b>ᴀɴɪᴍᴇ</b>\n"
        f"{anime}\n\n"

        f"🌐 <b>ʟᴀɴɢᴜᴀɢᴇ</b>\n"
        f"{language}\n\n"

        f"🎙 <b>ᴅᴜʙ</b>\n"
        f"{dub}\n\n"

        f"🎞 <b>sᴇᴀsᴏɴ</b>\n"
        f"{season}\n\n"

        f"📝 <b>ᴇxᴛʀᴀ ᴅᴇᴛᴀɪʟs</b>\n"
        f"{extra}\n"
        f"{tmdb_block}\n"
        "🟡 <b>sᴛᴀᴛᴜs:</b> ᴘᴇɴᴅɪɴɢ"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Added",
                    callback_data=f"req_added:{req_id}",
                    style="success"
                ),
                InlineKeyboardButton(
                    "🔄 Working",
                    callback_data=f"req_working:{req_id}",
                    style="primary"
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Not Possible",
                    callback_data=f"req_denied:{req_id}",
                    style="danger"
                ),
                InlineKeyboardButton(
                    "📝 Reply",
                    callback_data=f"req_reply:{req_id}",
                    style="primary"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Close",
                    callback_data=f"req_close:{req_id}",
                    style="danger"
                )
            ]
        ]
    )

    await context.bot.send_message(
        chat_id=REPORT_GROUP_ID,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    await update.message.reply_text(
        f"✅ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴜʙᴍɪᴛᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!\n\n"
        f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ: <code>{req_id}</code>\n\n"
        "ᴏᴜʀ ᴀᴅᴍɪɴs ᴡɪʟʟ ʀᴇᴠɪᴇᴡ ɪᴛ sᴏᴏɴ.",
        parse_mode="HTML",
    )

    context.user_data.clear()

    return ConversationHandler.END
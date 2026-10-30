import re
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from database.mongo import get_all_anime, add_anime_db
from utils.direct_filter import normalize
from utils.sudo import require_sudo


NAME, KEYS, LANGUAGE, HINDI, ENGLISH, STICKER, CONFIRM = range(7)

DRAFT = "mahiru_add_draft"
BUSY = "mahiru_add_busy"


def buttons(rows):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data)
         for text, data in row]
        for row in rows
    ])


def valid_url(value):
    return bool(re.fullmatch(
        r"https?://[^\s/]+\.[^\s/]+(?:/[^\s]*)?",
        value,
        re.IGNORECASE,
    ))


def clear_draft(context):
    context.user_data.pop(DRAFT, None)
    context.user_data.pop(BUSY, None)


async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_sudo(update, context):
        return ConversationHandler.END

    # This workflow is private to avoid exposing watch links.
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔒 Please use /add in my private chat."
        )
        return ConversationHandler.END

    context.user_data[DRAFT] = {}
    context.user_data[BUSY] = True

    await update.message.reply_text(
        "🎌 MAHIRU ANIME MANAGER\n\n"
        "Step 1/7\n"
        "Send the full anime name.\n\n"
        "Use /cancel to stop."
    )
    return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()

    if not name or len(name) > 200:
        await update.message.reply_text(
            "❌ Enter a valid anime name (maximum 200 characters)."
        )
        return NAME

    existing = await get_all_anime()

    if any(normalize(a.get("name")) == normalize(name) for a in existing):
        await update.message.reply_text(
            "❌ This anime already exists. Send another name."
        )
        return NAME

    context.user_data[DRAFT]["name"] = name

    await update.message.reply_text(
        "🔑 Step 2/7\n\n"
        "Send manually selected keywords separated by commas.\n\n"
        "Example:\nseven knights, marronnier"
    )
    return KEYS


async def receive_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text

    keys = list(dict.fromkeys(
        normalize(item)
        for item in raw.split(",")
        if normalize(item)
    ))

    if not keys or len(keys) > 30:
        await update.message.reply_text(
            "❌ Enter 1–30 valid keywords."
        )
        return KEYS

    if any(len(key) > 100 for key in keys):
        await update.message.reply_text(
            "❌ Each keyword must be at most 100 characters."
        )
        return KEYS

    existing = await get_all_anime()
    name = context.user_data[DRAFT]["name"]

    new_terms = set(keys) | {normalize(name)}

    for anime in existing:
        old_keys = anime.get("keys") or []

        if isinstance(old_keys, str):
            old_keys = old_keys.split(",")

        old_terms = {
            normalize(item)
            for item in [anime.get("name", "")] + list(old_keys)
        }

        if new_terms & old_terms:
            await update.message.reply_text(
                "❌ A keyword or anime name conflicts with an "
                "existing anime.\n\nPlease send different keywords."
            )
            return KEYS

    context.user_data[DRAFT]["keys"] = keys

    await update.message.reply_text(
        "🌐 Step 3/7\nSelect available languages:",
        reply_markup=buttons([
            [("🇮🇳 Hindi", "addlang:hindi")],
            [("🇬🇧 English", "addlang:english")],
            [("🌐 Both", "addlang:both")],
        ])
    )
    return LANGUAGE


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data.split(":", 1)[1]

    context.user_data[DRAFT]["language"] = choice

    await query.edit_message_text(
        f"✅ Selected: {choice.title()}"
    )

    if choice in ("hindi", "both"):
        await query.message.reply_text(
            "🇮🇳 Step 4/7\nSend the Hindi watch link."
        )
        return HINDI

    await query.message.reply_text(
        "🇬🇧 Step 4/7\nSend the English watch link."
    )
    return ENGLISH


async def receive_hindi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL. Send a complete HTTPS watch link."
        )
        return HINDI

    context.user_data[DRAFT]["hindi_link"] = url

    if context.user_data[DRAFT]["language"] == "both":
        await update.message.reply_text(
            "🇬🇧 Step 5/7\nSend the English watch link."
        )
        return ENGLISH

    await update.message.reply_text(
        "🎭 Send your search-result sticker now.\n\n"
        "You may also send its Telegram file ID."
    )
    return STICKER


async def receive_english(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL. Send a complete HTTPS watch link."
        )
        return ENGLISH

    context.user_data[DRAFT]["english_link"] = url

    await update.message.reply_text(
        "🎭 Step 6/7\n\n"
        "Send your search-result sticker or its file ID."
    )
    return STICKER


async def receive_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if message.sticker:
        sticker_id = message.sticker.file_id

    elif message.text:
        sticker_id = message.text.strip()

        if not sticker_id or len(sticker_id) > 512:
            await message.reply_text("❌ Invalid sticker ID.")
            return STICKER

        try:
            await context.bot.get_file(sticker_id)
        except Exception:
            await message.reply_text(
                "❌ Telegram couldn't verify this sticker file ID. "
                "Please forward the actual sticker instead."
            )
            return STICKER

    else:
        await message.reply_text(
            "❌ Please send a sticker or sticker file ID."
        )
        return STICKER

    context.user_data[DRAFT]["sticker"] = sticker_id
    data = context.user_data[DRAFT]

    preview = (
        "🎌 <b>CONFIRM ANIME</b>\n\n"
        f"🎬 <b>Name:</b> {escape(data['name'])}\n"
        f"🔑 <b>Keywords:</b> {escape(', '.join(data['keys']))}\n"
        f"🌐 <b>Language:</b> {escape(data['language'].title())}\n"
        f"🇮🇳 Hindi: {'✅' if data.get('hindi_link') else '❌'}\n"
        f"🇬🇧 English: {'✅' if data.get('english_link') else '❌'}\n"
        "🎭 Sticker: ✅\n\n"
        "Save this anime?"
    )

    await message.reply_text(
        preview,
        parse_mode="HTML",
        reply_markup=buttons([
            [("✅ Save Anime", "addconfirm:save")],
            [("❌ Cancel", "addconfirm:cancel")],
        ])
    )

    return CONFIRM


async def confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "addconfirm:cancel":
        clear_draft(context)
        await query.edit_message_text("❌ Anime addition cancelled.")
        return ConversationHandler.END

    data = context.user_data.get(DRAFT)

    if not data:
        await query.edit_message_text(
            "❌ Session expired. Please start /add again."
        )
        clear_draft(context)
        return ConversationHandler.END

    # Recheck before saving.
    existing = await get_all_anime()

    new_terms = set(data["keys"]) | {normalize(data["name"])}

    for anime in existing:
        old_keys = anime.get("keys") or []

        if isinstance(old_keys, str):
            old_keys = old_keys.split(",")

        old_terms = {
            normalize(item)
            for item in [anime.get("name", "")] + list(old_keys)
        }

        if new_terms & old_terms:
            await query.edit_message_text(
                "❌ This anime or one of its keywords now exists. "
                "Please restart /add."
            )
            clear_draft(context)
            return ConversationHandler.END

    try:
        await add_anime_db(
            name=data["name"],
            keys=data["keys"],
            sticker=data["sticker"],
            hindi_link=data.get("hindi_link"),
            english_link=data.get("english_link"),
        )
    except Exception:
        await query.edit_message_text(
            "❌ Database save failed. Please check the bot logs."
        )
        clear_draft(context)
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ Anime saved successfully!\n\n"
        f"🎬 {data['name']}\n"
        f"🔑 {', '.join(data['keys'])}\n\n"
        "Your anime is now available for direct search."
    )

    clear_draft(context)
    return ConversationHandler.END


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_draft(context)
    await update.message.reply_text("❌ Anime addition cancelled.")
    return ConversationHandler.END


anime_add_handler = ConversationHandler(
    entry_points=[
        CommandHandler("add", start_add),
    ],
    states={
        NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
        ],
        KEYS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_keys)
        ],
        LANGUAGE: [
            CallbackQueryHandler(
                choose_language,
                pattern=r"^addlang:(hindi|english|both)$"
            )
        ],
        HINDI: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_hindi)
        ],
        ENGLISH: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_english)
        ],
        STICKER: [
            MessageHandler(
                (filters.Sticker.ALL | filters.TEXT) & ~filters.COMMAND,
                receive_sticker
            )
        ],
        CONFIRM: [
            CallbackQueryHandler(
                confirm_add,
                pattern=r"^addconfirm:(save|cancel)$"
            )
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_add),
    ],
    allow_reentry=False,
          )

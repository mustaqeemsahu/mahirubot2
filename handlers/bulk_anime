# ==========================================
# MAHIRU BULK ANIME MANAGER
# Command: /bulkanime
# ==========================================

import logging
from html import escape
from urllib.parse import urlsplit

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

logger = logging.getLogger(__name__)

STICKER, RECORDS, CONFIRM = range(3)

DRAFT = "mahiru_bulk_draft"
BUSY = "mahiru_bulk_busy"

MAX_RECORDS = 50


# ==========================================
# HELPERS
# ==========================================

def clear_bulk(context):
    context.user_data.pop(DRAFT, None)
    context.user_data.pop(BUSY, None)


def valid_url(value):
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not any(c.isspace() for c in value)
            and len(value) <= 2048
        )
    except ValueError:
        return False


def anime_terms(anime):
    keys = anime.get("keys") or []

    if isinstance(keys, str):
        keys = keys.split(",")

    return {
        normalize(value)
        for value in [anime.get("name", "")] + list(keys)
        if normalize(value)
    }


def parse_record(line):
    parts = [p.strip() for p in line.split("|")]

    if len(parts) != 5:
        raise ValueError("Expected exactly 5 fields")

    name, raw_keys, language, hindi, english = parts

    if not name or len(name) > 200:
        raise ValueError("Invalid anime name")

    keys = list(dict.fromkeys(
        normalize(k)
        for k in raw_keys.split(",")
        if normalize(k)
    ))

    if not 1 <= len(keys) <= 30:
        raise ValueError("Provide 1–30 keywords")

    if any(len(k) > 100 for k in keys):
        raise ValueError("Keyword exceeds 100 characters")

    language = language.upper()

    if language not in ("HINDI", "ENGLISH", "BOTH"):
        raise ValueError("Language must be HINDI, ENGLISH or BOTH")

    if language == "HINDI":
        if not valid_url(hindi) or english != "-":
            raise ValueError("Invalid Hindi-only links")
        english = None

    elif language == "ENGLISH":
        if hindi != "-" or not valid_url(english):
            raise ValueError("Invalid English-only links")
        hindi = None

    else:
        if not valid_url(hindi) or not valid_url(english):
            raise ValueError("Both watch links are required")

    return {
        "name": name,
        "keys": keys,
        "language": language,
        "hindi_link": hindi,
        "english_link": english,
    }


# ==========================================
# START COMMAND
# ==========================================

async def start_bulk(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await require_sudo(update, context):
        return ConversationHandler.END

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔒 Please use /bulkanime in my private chat."
        )
        return ConversationHandler.END

    if context.user_data.get("mahiru_add_busy"):
        await update.message.reply_text(
            "Finish or cancel your current /add session first."
        )
        return ConversationHandler.END

    context.user_data[DRAFT] = {}
    context.user_data[BUSY] = True

    await update.message.reply_text(
        "🎌 MAHIRU BULK ANIME MANAGER\n\n"
        "Step 1/3\n\n"
        "Send the sticker you want to use for these anime.\n\n"
        "You can forward a sticker or send its file ID.\n\n"
        "Use /cancel to stop."
    )

    return STICKER


# ==========================================
# RECEIVE SHARED STICKER
# ==========================================

async def receive_bulk_sticker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message

    if message.sticker:
        sticker_id = message.sticker.file_id

    elif message.text:
        sticker_id = message.text.strip()

        try:
            if not sticker_id or len(sticker_id) > 512:
                raise ValueError("Invalid ID")

            await context.bot.get_file(sticker_id)

        except Exception:
            await message.reply_text(
                "❌ Invalid file ID.\n"
                "Please send the actual sticker instead."
            )
            return STICKER

    else:
        await message.reply_text(
            "❌ Send a sticker or sticker file ID."
        )
        return STICKER

    context.user_data[DRAFT]["sticker"] = sticker_id

    await message.reply_text(
        "✅ Sticker received!\n\n"
        "Step 2/3 — Send anime records.\n\n"
        "Format:\n"
        "Name | keywords | language | Hindi URL | English URL\n\n"
        "Example:\n"
        "Naruto | naruto, naruto classic | BOTH | "
        "https://example.com/hi | https://example.com/en\n\n"
        "Send up to 50 anime in one message.\n"
        "Use - for unavailable links."
    )

    return RECORDS


# ==========================================
# VALIDATE RECORDS
# ==========================================

async def receive_bulk_records(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message

    lines = [
        line.strip()
        for line in message.text.splitlines()
        if line.strip()
    ]

    if not lines or len(lines) > MAX_RECORDS:
        await message.reply_text(
            f"❌ Send between 1 and {MAX_RECORDS} anime records."
        )
        return RECORDS

    existing = await get_all_anime()

    used_terms = set()

    for anime in existing:
        used_terms.update(anime_terms(anime))

    valid = []
    errors = []

    for number, line in enumerate(lines, 1):
        try:
            anime = parse_record(line)
            terms = anime_terms(anime)

            conflict = terms & used_terms

            if conflict:
                raise ValueError(
                    "Duplicate name/keyword: "
                    + ", ".join(sorted(conflict)[:3])
                )

            used_terms.update(terms)
            valid.append(anime)

        except ValueError as error:
            errors.append(f"Line {number}: {error}")

    if errors:
        report = (
            "❌ BULK VALIDATION FAILED\n\n"
            + "\n".join(errors)
            + "\n\nNothing has been saved.\n"
            "Correct the records and send the complete list again."
        )

        await message.reply_text(report[:4000])
        return RECORDS

    context.user_data[DRAFT]["records"] = valid

    preview = [
        "🎌 BULK ANIME PREVIEW",
        "",
        f"Total anime: {len(valid)}",
        "Sticker: Received ✅",
        "",
    ]

    for index, anime in enumerate(valid, 1):
        preview.append(
            f"{index}. {anime['name']} [{anime['language']}]"
        )

    preview.extend([
        "",
        "All records passed validation.",
        "Confirm to save them to MongoDB."
    ])

    await message.reply_text(
        "\n".join(preview)[:4000],
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Save All Anime",
                    callback_data="bulkanime:save"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancel",
                    callback_data="bulkanime:cancel"
                )
            ]
        ])
    )

    return CONFIRM


# ==========================================
# CONFIRM AND SAVE
# ==========================================

async def confirm_bulk(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if query.data == "bulkanime:cancel":
        clear_bulk(context)

        await query.edit_message_text(
            "❌ Bulk anime addition cancelled."
        )
        return ConversationHandler.END

    draft = context.user_data.get(DRAFT)

    if not draft or not draft.get("records"):
        clear_bulk(context)

        await query.edit_message_text(
            "❌ Session expired. Start /bulkanime again."
        )
        return ConversationHandler.END

    records = draft["records"]
    sticker = draft["sticker"]

    # Recheck existing records before saving.
    existing = await get_all_anime()
    used_terms = set()

    for anime in existing:
        used_terms.update(anime_terms(anime))

    for anime in records:
        terms = anime_terms(anime)

        if terms & used_terms:
            clear_bulk(context)

            await query.edit_message_text(
                "❌ A duplicate was detected before saving.\n"
                "No anime was saved. Restart /bulkanime."
            )
            return ConversationHandler.END

        used_terms.update(terms)

    await query.edit_message_text(
        "⏳ Saving anime to MongoDB..."
    )

    success = 0
    failed = []

    for anime in records:
        try:
            await add_anime_db(
                name=anime["name"],
                keys=anime["keys"],
                sticker=sticker,
                hindi_link=anime["hindi_link"],
                english_link=anime["english_link"],
            )

            success += 1

        except Exception:
            logger.exception(
                "Bulk anime save failed: %s",
                anime["name"]
            )

            failed.append(anime["name"])

    report = (
        "🎌 MAHIRU BULK ADD REPORT\n\n"
        f"📦 Total: {len(records)}\n"
        f"✅ Saved: {success}\n"
        f"❌ Failed: {len(failed)}"
    )

    if failed:
        report += (
            "\n\nFailed anime:\n"
            + "\n".join(failed)
        )

    clear_bulk(context)

    await query.message.reply_text(report[:4000])

    return ConversationHandler.END


# ==========================================
# CANCEL
# ==========================================

async def cancel_bulk(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    clear_bulk(context)

    await update.message.reply_text(
        "❌ Bulk anime session cancelled."
    )

    return ConversationHandler.END


# ==========================================
# CONVERSATION HANDLER
# ==========================================

bulk_anime_handler = ConversationHandler(
    entry_points=[
        CommandHandler("bulkanime", start_bulk)
    ],

    states={
        STICKER: [
            MessageHandler(
                (filters.Sticker.ALL | filters.TEXT)
                & ~filters.COMMAND,
                receive_bulk_sticker
            )
        ],

        RECORDS: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_bulk_records
            )
        ],

        CONFIRM: [
            CallbackQueryHandler(
                confirm_bulk,
                pattern=r"^bulkanime:(save|cancel)$"
            )
        ],
    },

    fallbacks=[
        CommandHandler("cancel", cancel_bulk)
    ],

    allow_reentry=False,
)

# ==============================
# START HANDLER
# ==============================

import asyncio
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    REPORT_GROUP_ID,
    START_PHOTO,
    WELCOME_EMOJIS,
    START_ANIMATION_ENABLED,
    START_PRIVATE_ANIMATION,
    START_GROUP_ANIMATION,
    START_EMOJI_ENABLED,
    START_STICKER_ENABLED,
    START_TEXT_ANIMATION_ENABLED,
    START_ANIMATION_TEXTS,
    START_EMOJI_DELETE_DELAY,
    START_STICKER_DELETE_DELAY,
    START_TEXT_DELETE_DELAY,
)
from database.mongo import add_user, get_start_sticker
from utils.helpers import now


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
# SAFE DELETE HELPERS
# ==============================

async def _safe_delete(bot, chat_id, message_id):
    """Delete a message. Never raises."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


# ==============================
# ANIMATION TASK
# ==============================

async def _run_start_animation(
    bot,
    chat_id,
    final_sender,
):
    """
    Ordered cinematic /start animation.

    Sequence:
        emoji → wait → delete
        sticker → wait → delete
        temporary texts → wait → delete
        final main start message
    """
    try:
        # -------- 1. EMOJI --------
        if START_EMOJI_ENABLED:
            try:
                emoji = random.choice(WELCOME_EMOJIS)
                emoji_msg = await bot.send_message(
                    chat_id=chat_id,
                    text=emoji,
                )
                await asyncio.sleep(START_EMOJI_DELETE_DELAY)
                await _safe_delete(bot, chat_id, emoji_msg.message_id)
            except Exception as e:
                print(f"[START] Emoji stage failed: {e}")

        # -------- 2. STICKER --------
        if START_STICKER_ENABLED:
            try:
                sticker_id = await get_start_sticker()

                if sticker_id:
                    sticker_msg = await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=sticker_id,
                    )
                    await asyncio.sleep(START_STICKER_DELETE_DELAY)
                    await _safe_delete(bot, chat_id, sticker_msg.message_id)
            except Exception as e:
                print(f"[START] Sticker stage failed: {e}")

        # -------- 3. TEMPORARY TEXTS --------
        if START_TEXT_ANIMATION_ENABLED:
            text_message_ids = []
            try:
                for temp_text in START_ANIMATION_TEXTS:
                    try:
                        tmsg = await bot.send_message(
                            chat_id=chat_id,
                            text=temp_text,
                        )
                        text_message_ids.append(tmsg.message_id)
                    except Exception as e:
                        print(f"[START] Text send failed: {e}")

                if text_message_ids:
                    await asyncio.sleep(START_TEXT_DELETE_DELAY)

                for msg_id in text_message_ids:
                    await _safe_delete(bot, chat_id, msg_id)
            except Exception as e:
                print(f"[START] Text stage failed: {e}")

        # -------- 4. FINAL MAIN START MESSAGE --------
        try:
            await final_sender()
        except Exception as e:
            print(f"[START] Final message failed: {e}")

    except Exception as e:
        print(f"[START] Animation task failed: {e}")


# ==============================
# START COMMAND
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message
    user = update.effective_user

    if not message or not user:
        return

    is_private = update.effective_chat.type == "private"

    chat_type = "👤 ᴘʀɪᴠᴀᴛᴇ" if is_private else "👥 ɢʀᴏᴜᴘ"

    user_id = user.id

    # ✅ Save user in DB
    try:
        await add_user(user_id)
    except Exception as e:
        print(f"Add user error: {e}")

    # 🔥 Log to report group
    try:
        await context.bot.send_message(
            REPORT_GROUP_ID,
            f"🚀 <b>ʙᴏᴛ sᴛᴀʀᴛᴇᴅ</b>\n\n"
            f"📍 ᴛʏᴘᴇ: {chat_type}\n"
            f"👤 ᴜsᴇʀ: {user.first_name}\n"
            f"🆔 ɪᴅ: <code>{user_id}</code>\n"
            f"🕒 ᴛɪᴍᴇ: {now()}",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Log error: {e}")

    # ==========================================
    # FINAL MESSAGE BUILDER (closures over msg/user/keyboard)
    # ==========================================

    # 🔗 Buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 𝗨𝗽𝗱𝗮𝘁𝗲𝘀", url="https://t.me/Sahu_Bots", style="primary"),
            InlineKeyboardButton("💬 𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="https://t.me/Anime_Search_Zone", style="primary")
        ],
        [
            InlineKeyboardButton(
                "➕ 𝗔𝗱𝗱 𝗠𝗲 𝗧𝗼 𝗬𝗼𝘂𝗿 𝗚𝗿𝗼𝘂𝗽",
                url=f"https://t.me/{context.bot.username}?startgroup=true",
                style="success"
            )
        ]
    ])

    # 📝 Message
    text = (
        f"<b>◆ ʜᴇʏ {user.first_name}, ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴀɴɪᴍᴇ ꜱᴇᴀʀᴄʜᴇʀ ʙᴏᴛ</b>\n\n"
        "<b><blockquote>ɪ ᴄᴀɴ ʜᴇʟᴩ ʏᴏᴜ ᴛᴏ ꜰɪɴᴅ ʏᴏᴜʀ ᴀɴɪᴍᴇ. ᴊᴜꜱᴛ ᴛʏᴩᴇ ᴀɴɪᴍᴇ ɴᴀᴍᴇ ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴡᴀᴛᴄʜ</blockquote></b>\n\n"
        "<b><blockquote expandable>ᴀᴅᴅ ᴍᴇ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴩ ᴀɴᴅ ᴍᴀᴋᴇ ᴛʜᴀᴛ ꜱɪᴍᴩʟᴇ ɢʀᴏᴜᴩ ɪɴᴛᴏ ᴀɴɪᴍᴇ ꜰɪɴᴅɪɴɢ ɢʀᴏᴜᴩ ʙʏ ᴊᴜꜱᴛ ᴀᴅᴅɪɴɢ ᴍᴇ ᴛʜᴇʀᴇ. ɪ ᴡɪʟʟ ᴩʀᴏᴠɪᴅᴇ ᴀɴɪᴍᴇ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴩ ᴀʟꜱᴏ. ꜰʀᴏᴍ ᴛʜɪꜱ ʏᴏᴜʀ ᴍᴇᴍʙᴇʀꜱ ᴄᴀɴ ᴀʟꜱᴏ ᴇɴᴊᴏʏ ᴀɴɪᴍᴇ ᴛʜᴇʀᴇ. </blockquote></b>\n\n"
        "<b>◆ ᴍᴀɪɴ</b> :- @Anime_Stream_Zone"
    )

    # 📤 Send Message Safely
    async def _send_final():
        try:
            await message.reply_photo(
                photo=START_PHOTO,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML",
                has_spoiler=True,
            )
        except Exception as e:
            print(f"Photo send failed: {e}")
            try:
                await message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception as e2:
                print(f"Text fallback failed: {e2}")

    # ==========================================
    # PRIVATE / GROUP BRANCHING
    # ==========================================

    run_animation = (
        START_ANIMATION_ENABLED
        and (
            (is_private and START_PRIVATE_ANIMATION)
            or (not is_private and START_GROUP_ANIMATION)
        )
    )

    if run_animation:
        chat_id = update.effective_chat.id

        # Fire ONE background task controlling the full sequence
        asyncio.create_task(
            _run_start_animation(
                bot=context.bot,
                chat_id=chat_id,
                final_sender=_send_final,
            )
        )
        return

    # No animation: send final message immediately
    await _send_final()
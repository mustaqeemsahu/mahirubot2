"""Group join/leave events, member welcomes and silent member tracking."""

import html
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from config import (
    GROUP_PHOTO,
    MAIN_CHANNEL_URL,
    REPORT_GROUP_ID,
    SUPPORT_GROUP_URL,
    WELCOME_EMOJIS,
)
from database.mongo import add_group, remove_group, track_group_member
from utils.helpers import now


SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    """Convert ordinary Latin text to the project's small-caps style."""
    return str(text).translate(SMALL_CAPS)


def _group_keyboard(bot_username: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📢 Main Channel", url=MAIN_CHANNEL_URL),
            InlineKeyboardButton("💬 Support Group", url=SUPPORT_GROUP_URL),
        ]
    ]
    if bot_username:
        rows.append([
            InlineKeyboardButton(
                "➕ Add Me To Your Group",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])
    return InlineKeyboardMarkup(rows)


async def _send_group_intro(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the bot-added intro; fall back to text if the photo cannot be sent."""
    text = (
        "<b>✨ Thanks for adding Mahiru Anime Bot!</b>\n\n"
        "Your group's anime search assistant is ready. 🎌\n\n"
        "<b>How to use:</b>\n"
        "• Send an anime name directly in the group\n"
        "• Or use <code>/anime Naruto</code>\n"
        "• Use <code>/animelist</code> to browse saved anime\n"
        "• Use <code>/help</code> to see available commands\n\n"
        "<i>Search an anime and I'll share its available watch links.</i>\n\n"
        "📢 <b>Updates:</b> <a href=\"https://t.me/Anime_Stream_Zone\">ANIME STREAM ZONE</a>"
    )
    keyboard = _group_keyboard(getattr(context.bot, "username", None))

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=GROUP_PHOTO,
            caption=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as photo_error:
        print(f"[GROUP] Intro photo failed in {chat_id}: {photo_error}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as message_error:
            print(f"[GROUP] Intro message failed in {chat_id}: {message_error}")


async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle this bot being added to or removed from a group."""
    result = update.my_chat_member
    if result is None:
        return

    chat = result.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    changed_user = result.new_chat_member.user
    if changed_user.id != context.bot.id:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    active_statuses = {"member", "administrator", "restricted"}

    # Bot removed or blocked: remove the group from the broadcast database.
    if new_status in {"left", "kicked"}:
        try:
            await remove_group(chat.id)
        except Exception as exc:
            print(f"[GROUP] Could not remove group {chat.id}: {exc}")
        return

    # Only send the intro when the bot transitions from inactive to active.
    if old_status in active_statuses or new_status not in active_statuses:
        return

    try:
        await add_group(chat.id)
    except Exception as exc:
        print(f"[GROUP] Could not save group {chat.id}: {exc}")

    await _send_group_intro(chat.id, context)

    # Report logging must never prevent the group intro.
    adder = result.from_user
    try:
        member_count = await context.bot.get_chat_member_count(chat.id)
    except Exception:
        member_count = "Unknown"

    group_title = html.escape(chat.title or "Unknown Group")
    adder_name = html.escape(adder.full_name or adder.first_name or "Unknown")
    report_text = (
        "<b>🤖 Bot added to a group</b>\n\n"
        f"👥 <b>Group:</b> {group_title}\n"
        f"🆔 <b>Group ID:</b> <code>{chat.id}</code>\n"
        f"👤 <b>Added by:</b> <a href=\"tg://user?id={adder.id}\">{adder_name}</a>\n"
        f"👥 <b>Members:</b> {member_count}\n"
        f"🕒 <b>Time:</b> {html.escape(str(now()))}"
    )
    try:
        await context.bot.send_message(
            chat_id=REPORT_GROUP_ID,
            text=report_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as exc:
        print(f"[GROUP] Report logging failed for {chat.id}: {exc}")


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome real users joining a group and track every joining account."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    new_members = message.new_chat_members or []
    if not new_members:
        return

    group_title = html.escape(chat.title or "this group")

    for user in new_members:
        # Track bots too, because existing moderation/member tools may need them.
        try:
            await track_group_member(
                group_id=chat.id,
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_bot=user.is_bot,
            )
        except Exception as exc:
            print(f"[GROUP] Member tracking failed for {user.id} in {chat.id}: {exc}")

        # Do not send human-style welcomes to bots or the bot itself.
        if user.is_bot or user.id == context.bot.id:
            continue

        display_name = html.escape(user.full_name or user.first_name or "there")
        emoji = random.choice(WELCOME_EMOJIS) if WELCOME_EMOJIS else "👋"
        welcome_text = (
            f"{emoji} <b>Welcome, <a href=\"tg://user?id={user.id}\">{display_name}</a>!</b>\n\n"
            f"We're happy to have you in <b>{group_title}</b>. 🌸\n\n"
            "<b>🎌 Anime Search</b>\n"
            "• Send an anime name in the group to search\n"
            "• Or try <code>/anime Naruto</code>\n"
            "• Use <code>/animelist</code> to browse anime\n\n"
            "Enjoy your stay and have fun! ✨"
        )
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=welcome_text,
                parse_mode="HTML",
                reply_to_message_id=message.message_id,
                allow_sending_without_reply=True,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            print(f"[GROUP] Welcome message failed for {user.id} in {chat.id}: {exc}")


async def track_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently track group message senders without interrupting other handlers."""
    try:
        chat = update.effective_chat
        user = update.effective_user
        if chat is None or user is None or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        await track_group_member(
            group_id=chat.id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            is_bot=user.is_bot,
        )
    except Exception as exc:
        print(f"[GROUP] Message member tracking failed: {exc}")

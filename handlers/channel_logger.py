# ==============================
# CHANNEL ACTIVITY LOGGER
# ==============================

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

from config import OWNER_FORCE_CHANNEL_ID, REPORT_GROUP_ID
from utils.helpers import now


# ==============================
# SMALL CAPS HELPER
# ==============================

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


# ==============================
# REUSABLE LOGGER
# ==============================

async def log_channel_event(
    context: ContextTypes.DEFAULT_TYPE,
    event_type: str,
    user,
    chat,
    status_text: str,
):
    """
    Reusable channel activity logger.

    event_type examples (future use):
        "channel_join", "channel_leave"
        "user_start", "anime_search", "anime_request"
        "admin_action", "warning", "ban"

    Currently used only for:
        channel_join / channel_leave (Main Channel)

    Sends a formatted log to REPORT_GROUP_ID.
    Never raises.
    """
    try:
        user_id = getattr(user, "id", "Unknown")
        full_name = getattr(user, "full_name", None) or getattr(user, "first_name", "Unknown")

        chat_title = getattr(chat, "title", "Unknown Channel")
        chat_id = getattr(chat, "id", "Unknown")

        text = (
            f"📢 <b>{sc(event_type.replace('_', ' '))}</b>\n\n"
            f"👤 {sc('User')}: {full_name}\n"
            f"🆔 {sc('ID')}: <code>{user_id}</code>\n"
            f"📢 {sc('Channel')}: {chat_title}\n"
            f"🆔 {sc('Channel ID')}: <code>{chat_id}</code>\n"
            f"⏰ {sc('Time')}: {now()}\n\n"
            f"{status_text}"
        )

        await context.bot.send_message(
            chat_id=REPORT_GROUP_ID,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except Exception as e:
        print(f"[CHANNEL_LOGGER] Failed to send log: {e}")


# ==============================
# CHAT MEMBER UPDATE HANDLER
# ==============================

async def channel_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):

    result = update.chat_member

    if not result:
        return

    chat = result.chat

    # Only log for the permanent Main/Owner Channel
    if chat.id != OWNER_FORCE_CHANNEL_ID:
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    user = result.new_chat_member.user

    # Ignore bots
    if getattr(user, "is_bot", False):
        return

    joined_statuses = {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
        ChatMemberStatus.RESTRICTED,
    }

    left_statuses = {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED,
    }

    old_joined = old_status in joined_statuses
    new_joined = new_status in joined_statuses

    # JOIN event
    if (not old_joined) and new_joined:
        await log_channel_event(
            context=context,
            event_type="channel_join",
            user=user,
            chat=chat,
            status_text="✅ <b>sᴛᴀᴛᴜs:</b> ᴊᴏɪɴᴇᴅ",
        )
        return

    # LEAVE event
    if old_joined and new_status in left_statuses:
        await log_channel_event(
            context=context,
            event_type="channel_leave",
            user=user,
            chat=chat,
            status_text="❌ <b>sᴛᴀᴛᴜs:</b> ʟᴇғᴛ",
        )
        return
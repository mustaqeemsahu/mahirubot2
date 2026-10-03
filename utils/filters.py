# ==============================
# FILTERS
# ==============================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus

from config import (
    OWNER_FORCE_CHANNEL_ID,
    OWNER_FORCE_CHANNEL_LINK,
)
from database.mongo import get_promotional_channels
from utils.sudo import is_owner_or_sudo

BOT_STATUS = {"active": True}


# ==============================
# SMALL CAPS HELPERS
# ==============================

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


# ==============================
# BOT ON/OFF
# ==============================

async def check_bot_status(update: Update):
    if not BOT_STATUS["active"]:
        await update.message.reply_text("🚧 ʙᴏᴛ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ")
        return False
    return True


# ==============================
# MEMBERSHIP CHECK HELPERS
# ==============================

_ALLOWED_STATUSES = (
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.OWNER,
    ChatMemberStatus.RESTRICTED,
)


async def _is_member(bot, channel_id, user_id) -> bool:
    """
    Live membership check via Telegram.
    Returns True only if Telegram reports an allowed status.
    Returns False on any error (fail-closed).
    """
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in _ALLOWED_STATUSES
    except Exception as e:
        print(f"[FORCE_SUB] get_chat_member failed for {channel_id}: {e}")
        return False


# ==============================
# FORCE SUB
# ==============================

async def force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    # Owner and Sudo bypass force-sub
    if await is_owner_or_sudo(user_id):
        return True

    bot = context.bot

    # ---------- 1. MAIN OWNER CHANNEL ----------
    main_joined = await _is_member(bot, OWNER_FORCE_CHANNEL_ID, user_id)

    # ---------- 2. ACTIVE PROMOTIONAL CHANNELS ----------
    try:
        promos = await get_promotional_channels(active_only=True)
    except Exception as e:
        print(f"[FORCE_SUB] Failed to load promo channels: {e}")
        promos = []

    missing_promos = []
    for promo in promos:
        cid = promo.get("channel_id")
        if cid is None:
            continue
        joined = await _is_member(bot, cid, user_id)
        if not joined:
            missing_promos.append(promo)

    # ---------- 3. ALL JOINED? ----------
    if main_joined and not missing_promos:
        return True

    # ---------- 4. BUILD JOIN KEYBOARD ----------
    buttons = []

    if not main_joined:
        buttons.append(
            [
                InlineKeyboardButton(
                    "📢 Join Main Channel",
                    url=OWNER_FORCE_CHANNEL_LINK,
                    style="success",
                )
            ]
        )

    for promo in missing_promos:
        link = promo.get("channel_link")
        name = promo.get("name") or "Promo Channel"
        if link:
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"📢 Join {name}",
                        url=link,
                        style="success",
                    )
                ]
            )

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None

    # ---------- 5. DENY MESSAGE ----------
    deny_text = (
        "❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ!!!\n\n"
        "ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs ʙᴇʟᴏᴡ ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ.\n\n"
        "ᴛʜᴀɴᴋ ʏᴏᴜ & sᴜᴘᴘᴏʀᴛ ᴜs"
    )

    try:
        await update.message.reply_text(
            deny_text,
            reply_markup=keyboard,
        )
    except Exception as e:
        print(f"[FORCE_SUB] Deny message failed: {e}")

    return False
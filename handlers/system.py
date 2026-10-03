# ==============================
# SYSTEM MODULE
# ==============================
# Commands / triggers:
#   "mahiru ping"  → PUBLIC text trigger (case-insensitive exact)
#   /bstats        → OWNER + SUDO
#   /banall        → OWNER + SUDO (group only, direct)
#   /restart       → OWNER + SUDO (direct, process-level)
# ==============================

import asyncio
import logging
import os
import platform
import sys
import time

from html import escape
from importlib import metadata as importlib_metadata

from telegram import Update
from telegram.error import Forbidden, BadRequest, RetryAfter
from telegram.ext import ContextTypes

from config import PING_PHOTO, BSTATS_PHOTO, OWNER_ID

from utils.sudo import require_sudo, is_owner_or_sudo, is_sudo
from utils.filters import BOT_STATUS
from utils.uptime import START_TIME

from database.mongo import (
    total_users,
    total_groups,
    get_group_members,
    remove_group_member,
)


# ==============================
# LOGGER
# ==============================

logger = logging.getLogger(__name__)


# ==============================
# SAFE HELPERS
# ==============================

async def _safe_total_users() -> int:
    try:
        return int(await total_users())
    except Exception as e:
        logger.warning("total_users failed: %s", e)
        return 0


async def _safe_total_groups() -> int:
    try:
        return int(await total_groups())
    except Exception as e:
        logger.warning("total_groups failed: %s", e)
        return 0


def format_uptime(seconds: float) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        seconds = 0

    if seconds < 0:
        seconds = 0

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def get_current_uptime() -> str:
    return format_uptime(time.time() - START_TIME)


def _package_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except Exception:
        return None


def _safe_package_line(display_name: str, pip_name: str) -> str | None:
    version = _package_version(pip_name)
    if not version:
        return None
    return f"<code>{escape(display_name)} {escape(version)}</code>"


# ==============================
# "mahiru ping" — PUBLIC TEXT TRIGGER
# ==============================

MAHIRU_PING_TRIGGER = "mahiru ping"


def is_mahiru_ping(message) -> bool:
    """
    True iff the message text (stripped, lowercased) equals "mahiru ping".
    Safe against non-text / missing messages.
    """
    if message is None:
        return False

    text = getattr(message, "text", None)
    if not text:
        return False

    return text.strip().lower() == MAHIRU_PING_TRIGGER


async def mahiru_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message
    if message is None:
        return

    # Double-guard: only react to the exact phrase.
    if not is_mahiru_ping(message):
        return

    try:
        start = time.perf_counter()
        await context.bot.get_me()
        latency_ms = int((time.perf_counter() - start) * 1000)
    except Exception as e:
        logger.warning("mahiru_ping get_me failed: %s", e)
        latency_ms = -1

    uptime = get_current_uptime()

    status = "🟢 ᴏɴʟɪɴᴇ" if BOT_STATUS.get("active", True) else "🔴 ᴏғғʟɪɴᴇ"

    if latency_ms >= 0:
        latency_line = f"⚡ <b>ᴘɪɴɢ:</b> <code>{latency_ms} ms</code>"
    else:
        latency_line = "⚡ <b>ᴘɪɴɢ:</b> <code>ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ</code>"

    caption = (
        "🏓 <b>ᴘᴏɴɢ!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{latency_line}\n"
        f"⏱️ <b>ᴜᴘᴛɪᴍᴇ:</b> <code>{uptime}</code>\n"
        f"🟢 <b>sᴛᴀᴛᴜs:</b> {status}\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    if PING_PHOTO:
        try:
            await message.reply_photo(
                photo=PING_PHOTO,
                has_spoiler=True,
                caption=caption,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            logger.warning("mahiru_ping photo failed: %s", e)

    try:
        await message.reply_text(
            caption,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning("mahiru_ping text failed: %s", e)


# ==============================
# /bstats — OWNER + SUDO
# ==============================

async def bstats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    users = await _safe_total_users()
    groups = await _safe_total_groups()
    uptime = get_current_uptime()
    status = "🟢 ᴏɴʟɪɴᴇ" if BOT_STATUS.get("active", True) else "🔴 ᴏғғʟɪɴᴇ"

    try:
        me = await context.bot.get_me()
        bot_username = me.username or "unknown"
        bot_id = me.id
    except Exception as e:
        logger.warning("bstats get_me failed: %s", e)
        bot_username = "unknown"
        bot_id = 0

    py_version = platform.python_version()
    os_name = platform.system()
    os_release = platform.release()
    arch = platform.machine() or "Unknown"

    try:
        cpu = platform.processor() or "Unknown"
    except Exception:
        cpu = "Unknown"

    module_lines = []
    for display, pip_name in (
        ("python-telegram-bot", "python-telegram-bot"),
        ("motor", "motor"),
        ("pymongo", "pymongo"),
        ("aiohttp", "aiohttp"),
        ("python-dotenv", "python-dotenv"),
    ):
        line = _safe_package_line(display, pip_name)
        if line:
            module_lines.append(line)

    modules_block = "\n".join(module_lines) if module_lines else "<i>ɴᴏ ᴍᴏᴅᴜʟᴇ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</i>"

    caption = (
        "🤖 <b>ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🤖 <b>ʙᴏᴛ:</b> @{escape(bot_username)}\n"
        f"🆔 <b>ʙᴏᴛ ɪᴅ:</b> <code>{bot_id}</code>\n\n"

        f"👤 <b>ᴜsᴇʀs:</b> <code>{users}</code>\n"
        f"👥 <b>ɢʀᴏᴜᴘs:</b> <code>{groups}</code>\n\n"

        f"⏱️ <b>ᴜᴘᴛɪᴍᴇ:</b> <code>{uptime}</code>\n"
        f"🟢 <b>sᴛᴀᴛᴜs:</b> {status}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🖥️ <b>sʏsᴛᴇᴍ ɪɴғᴏʀᴍᴀᴛɪᴏɴ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🐍 <b>ᴘʏᴛʜᴏɴ:</b> <code>{escape(py_version)}</code>\n"
        f"💻 <b>ᴏs:</b> <code>{escape(os_name)} {escape(os_release)}</code>\n"
        f"🏗️ <b>ᴀʀᴄʜɪᴛᴇᴄᴛᴜʀᴇ:</b> <code>{escape(arch)}</code>\n"
        f"⚙️ <b>ᴄᴘᴜ:</b> <code>{escape(cpu)}</code>\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📦 <b>ᴘʏᴛʜᴏɴ ᴍᴏᴅᴜʟᴇs</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{modules_block}\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    if BSTATS_PHOTO:
        try:
            await update.message.reply_photo(
                photo=BSTATS_PHOTO,
                has_spoiler=True,
                caption=caption,
                parse_mode="HTML",
            )
            return
        except Exception as e:
            logger.warning("bstats photo failed: %s", e)

    await update.message.reply_text(
        caption,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ==============================
# /banall — OWNER + SUDO (group only, direct)
# ==============================

async def _can_restrict(bot, chat_id: int, user_id: int) -> bool:
    """Return True if the bot can actually restrict this member."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if getattr(member, "status", None) in ("administrator", "creator"):
            return False

        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if getattr(bot_member, "status", None) not in ("administrator", "creator"):
            return False

        if not getattr(bot_member, "can_restrict_members", False):
            return False

        return True
    except Exception:
        return False


async def _safe_ban(bot, chat_id: int, user_id: int) -> str:
    """Return 'banned' on success, 'failed' otherwise."""
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        return "banned"
    except RetryAfter as e:
        try:
            await asyncio.sleep(e.retry_after)
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            return "banned"
        except Exception:
            return "failed"
    except (Forbidden, BadRequest):
        return "failed"
    except Exception:
        return "failed"


async def banall(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    chat = update.effective_chat
    user = update.effective_user

    # Group only
    if chat.type not in ("group", "supergroup"):
        return await update.message.reply_text(
            "❌ <b>ɢʀᴏᴜᴘ ᴏɴʟʏ</b>\n\n"
            "ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴄᴀɴ ᴏɴʟʏ ʙᴇ ᴜsᴇᴅ ɪɴsɪᴅᴇ ᴀ ɢʀᴏᴜᴘ.",
            parse_mode="HTML",
        )

    # Bot permission check
    try:
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        is_admin = getattr(bot_member, "status", None) in ("administrator", "creator")
        can_restrict = getattr(bot_member, "can_restrict_members", False)

        if not is_admin or not can_restrict:
            return await update.message.reply_text(
                "❌ <b>ᴘᴇʀᴍɪssɪᴏɴ ᴇʀʀᴏʀ</b>\n\n"
                "ɪ ɴᴇᴇᴅ ᴀᴅᴍɪɴɪsᴛʀᴀᴛᴏʀ ᴘᴇʀᴍɪssɪᴏɴs ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴏᴘᴇʀᴀᴛɪᴏɴ.",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.warning("banall permission check failed: %s", e)
        return await update.message.reply_text(
            "❌ <b>ᴘᴇʀᴍɪssɪᴏɴ ᴇʀʀᴏʀ</b>\n\n"
            "ᴄᴏᴜʟᴅ ɴᴏᴛ ᴠᴇʀɪғʏ ʙᴏᴛ ᴘᴇʀᴍɪssɪᴏɴs.",
            parse_mode="HTML",
        )

    requester_name = escape(user.first_name or "Unknown")
    requester_url = f"tg://user?id={user.id}"

    await update.message.reply_text(
        "🔥 <b>ʙᴀɴᴀʟʟ sᴛᴀʀᴛᴇᴅ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b>\n"
        f"<a href=\"{requester_url}\">{requester_name}</a>\n\n"
        "⏳ <b>sᴛᴀᴛᴜs:</b> ᴘʀᴏᴄᴇssɪɴɢ...\n\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
    )

    # ---------- Protected sets ----------

    protected_ids = set()

    # Bot itself
    protected_ids.add(context.bot.id)

    # Owner
    try:
        protected_ids.add(int(OWNER_ID))
    except Exception:
        pass

    # Telegram group admins and owner
    admin_status_by_id = {}
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            m = getattr(admin, "user", None)
            if m is not None:
                protected_ids.add(m.id)
                admin_status_by_id[m.id] = getattr(admin, "status", None)
    except Exception as e:
        logger.warning("banall get_chat_administrators failed: %s", e)

    # Sudo users: check per candidate later, but we pre-filter what we can
    # (batch check not available; do it inside the loop)

    # ---------- Candidates from tracking collection ----------

    try:
        tracked = await get_group_members(chat.id)
    except Exception as e:
        logger.warning("banall get_group_members failed: %s", e)
        tracked = []

    # Deduplicate by user_id
    seen = set()
    candidates = []
    for doc in tracked:
        uid = doc.get("user_id")
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            continue
        if uid in seen:
            continue
        seen.add(uid)
        candidates.append(uid)

    logger.info(
        "BANALL group=%s candidates=%s",
        chat.id,
        len(candidates),
    )

    # ---------- Process ----------

    removed = 0
    skipped = 0
    protected = 0
    failed = 0

    eligible_count = 0

    for uid in candidates:

        # Protected: bot itself, Owner, group admin/creator
        if uid in protected_ids:
            protected += 1
            continue

        # Protected: Sudo
        try:
            if await is_owner_or_sudo(uid):
                protected += 1
                continue
        except Exception:
            protected += 1
            continue

        # Verify live Telegram status
        try:
            gm = await context.bot.get_chat_member(chat.id, uid)
        except Exception:
            # user may have left or be unreachable — clean up tracking
            try:
                await remove_group_member(chat.id, uid)
            except Exception:
                pass
            skipped += 1
            continue

        gstatus = getattr(gm, "status", None)

        if gstatus in ("left", "kicked"):
            # No longer a member — clean tracking, don't count as removal
            try:
                await remove_group_member(chat.id, uid)
            except Exception:
                pass
            skipped += 1
            continue

        if gstatus in ("administrator", "creator"):
            protected += 1
            continue

        # Can the bot actually restrict them?
        if not await _can_restrict(context.bot, chat.id, uid):
            protected += 1
            continue

        eligible_count += 1

        # Attempt ban
        result = await _safe_ban(context.bot, chat.id, uid)

        if result == "banned":
            removed += 1
            try:
                await remove_group_member(chat.id, uid)
            except Exception:
                pass
        else:
            failed += 1

        # Light pacing
        await asyncio.sleep(0.1)

    logger.info(
        "BANALL group=%s protected=%s eligible=%s removed=%s failed=%s skipped=%s",
        chat.id,
        protected,
        eligible_count,
        removed,
        failed,
        skipped,
    )

    await update.message.reply_text(
        "🔥 <b>ʙᴀɴᴀʟʟ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b>\n"
        f"<a href=\"{requester_url}\">{requester_name}</a>\n\n"
        f"✅ <b>ʀᴇᴍᴏᴠᴇᴅ:</b> <code>{removed}</code>\n"
        f"⏭️ <b>sᴋɪᴘᴘᴇᴅ:</b> <code>{skipped}</code>\n"
        f"🛡️ <b>ᴘʀᴏᴛᴇᴄᴛᴇᴅ:</b> <code>{protected}</code>\n"
        f"❌ <b>ғᴀɪʟᴇᴅ:</b> <code>{failed}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 <b>sᴛᴀᴛᴜs:</b> ᴄᴏᴍᴘʟᴇᴛᴇᴅ",
        parse_mode="HTML",
    )


# ==============================
# /restart — OWNER + SUDO (direct)
# ==============================

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    user = update.effective_user
    requester_name = escape(user.first_name or "Unknown")
    requester_url = f"tg://user?id={user.id}"

    try:
        await update.message.reply_text(
            "🔄 <b>ʀᴇsᴛᴀʀᴛɪɴɢ ʙᴏᴛ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ:</b>\n"
            f"<a href=\"{requester_url}\">{requester_name}</a>\n\n"
            "⚙️ <b>sᴛᴀᴛᴜs:</b> ʀᴇsᴛᴀʀᴛɪɴɢ...\n\n"
            "━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("restart pre-message failed: %s", e)

    await asyncio.sleep(0.5)

    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.exception("restart execv failed: %s", e)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    "❌ <b>ʀᴇsᴛᴀʀᴛ ғᴀɪʟᴇᴅ</b>\n\n"
                    "ᴛʜᴇ ʙᴏᴛ ᴄᴏᴜʟᴅ ɴᴏᴛ ʀᴇsᴛᴀʀᴛ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
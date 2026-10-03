import asyncio
import time

from html import escape

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import (
    RetryAfter,
    Forbidden,
    BadRequest,
)

from utils.uptime import START_TIME
from database.mongo import (
    get_all_users,
    get_all_groups,
    users_col,
    groups_col,
    remove_user,
    remove_group,
    total_groups,
    set_start_sticker,
    clear_start_sticker,
    add_promotional_channel,
    get_promotional_channels,
    remove_promotional_channel,
    channel_exists,
    add_sudo_user,
    remove_sudo_user,
    is_sudo_user,
    get_all_sudo_users,
    total_sudo_users,
)
from utils.sudo import require_sudo, require_owner
from config import OWNER_ID


# ==============================
# SMALL CAPS MAPPING
# ==============================

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


# ============================================================
# STATS
# ============================================================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_sudo(update, context):
        return

    users = await get_all_users()
    groups = await get_all_groups()

    await update.message.reply_text(
        f"📊 sᴛᴀᴛs\n\n"
        f"👤 ᴜsᴇʀs : {len(users)}\n"
        f"👥 ɢʀᴏᴜᴘs : {len(groups)}"
    )

# ===========================
# /groups
# ===========================

async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    all_groups = await get_all_groups()

    if not all_groups:
        return await update.message.reply_text("❌ ɴᴏ ɢʀᴏᴜᴘs ғᴏᴜɴᴅ.")

    PER_PAGE = 5
    page = 0

    start = page * PER_PAGE
    end = start + PER_PAGE

    text = (
        f"🏘 <b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs :</b> {await total_groups()}\n"
        f"📄 <b>ᴘᴀɢᴇ :</b> {page+1}\n\n"
    )

    valid_groups = []

    for chat_id in all_groups[start:end]:

        if not chat_id:
            continue

        try:
            chat = await context.bot.get_chat(chat_id)
            members = await context.bot.get_chat_member_count(chat_id)
            me = await context.bot.get_chat_member(chat_id, context.bot.id)

            status = "👑 ᴀᴅᴍɪɴ" if me.status == "administrator" else "👤 ᴍᴇᴍʙᴇʀ"

            invite = "ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ"

            try:
                if me.status == "administrator":
                    invite = chat.invite_link or "ɴᴏ ɪɴᴠɪᴛᴇ ʟɪɴᴋ"
            except:
                pass

            text += (
                f"📌 <b>{chat.title}</b>\n"
                f"🆔 <code>{chat.id}</code>\n"
                f"👥 {members} ᴍᴇᴍʙᴇʀs\n"
                f"🤖 {status}\n"
                f"🔗 {invite}\n\n"
            )

            valid_groups.append(chat_id)

        except Exception:

            await remove_group(chat_id)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➡ Next",
                    callback_data=f"groups_{page+1}",
                    style="primary"
                )
            ]
        ]
    )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=keyboard
    )

# ============================================================
# Uptime Handler
# ============================================================

async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    uptime_seconds = int(time.time() - START_TIME)

    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60

    text = (
        "🤖 <b>ʙᴏᴛ ᴜᴘᴛɪᴍᴇ</b>\n\n"
        f"🗓️ ᴅᴀʏs: <b>{days}</b>\n"
        f"🕒 ʜᴏᴜʀs: <b>{hours}</b>\n"
        f"⏰ ᴍɪɴᴜᴛᴇs: <b>{minutes}</b>\n"
        f"⌛ sᴇᴄᴏɴᴅs: <b>{seconds}</b>"
    )

    await update.message.reply_text(text, parse_mode="HTML")

# ============================================================
# Helper Function - Copy Message
# ============================================================

async def _copy_message(context, msg, chat_id, pin=False):
    """
    Copy `msg` to `chat_id`.

    Returns True iff the MESSAGE was delivered.
    Pin failure is optional and does NOT count as delivery failure.

    DB cleanup only occurs for errors that reliably indicate
    the recipient is permanently unreachable.
    """

    async def _attempt():
        try:
            return await msg.copy(chat_id=chat_id)

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            return await msg.copy(chat_id=chat_id)

        except Forbidden:
            # Bot blocked / kicked / lost rights
            if str(chat_id).startswith("-100"):
                await remove_group(chat_id)
            else:
                await remove_user(chat_id)
            return None

        except BadRequest as e:
            err = str(e).lower()

            # Only clean DB on clearly permanent failures
            permanent_markers = (
                "chat not found",
                "bot was blocked",
                "user is deactivated",
                "kicked",
                "not enough rights",
                "peer_id_invalid",
                "bot was kicked",
            )

            if any(marker in err for marker in permanent_markers):
                if str(chat_id).startswith("-100"):
                    await remove_group(chat_id)
                else:
                    await remove_user(chat_id)

            return None

        except Exception:
            return None

    try:
        sent = await _attempt()
    except Exception:
        return False

    if sent is None:
        return False

    # Optional pin — never affects delivery result
    if pin:
        try:
            await context.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent.message_id,
                disable_notification=True,
            )
        except Exception:
            pass

    return True

# ============================================================
# Helper Function - Forward Message
# ============================================================

async def _forward_message(context, msg, chat_id, pin=False):
    """
    Forward `msg` to `chat_id`.

    Returns True iff the MESSAGE was forwarded.
    Pin failure is optional and does NOT count as delivery failure.
    """

    async def _attempt():
        try:
            return await context.bot.forward_message(
                chat_id=chat_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
            )

        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)
            return await context.bot.forward_message(
                chat_id=chat_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
            )

        except Forbidden:
            if str(chat_id).startswith("-100"):
                await remove_group(chat_id)
            else:
                await remove_user(chat_id)
            return None

        except BadRequest as e:
            err = str(e).lower()

            permanent_markers = (
                "chat not found",
                "bot was blocked",
                "user is deactivated",
                "kicked",
                "not enough rights",
                "peer_id_invalid",
                "bot was kicked",
            )

            if any(marker in err for marker in permanent_markers):
                if str(chat_id).startswith("-100"):
                    await remove_group(chat_id)
                else:
                    await remove_user(chat_id)

            return None

        except Exception:
            return None

    try:
        sent = await _attempt()
    except Exception:
        return False

    if sent is None:
        return False

    if pin:
        try:
            await context.bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent.message_id,
                disable_notification=True,
            )
        except Exception:
            pass

    return True


# ============================================================
# Broadcast Report
# ============================================================

async def _send_report(
    update,
    context,
    users_total,
    users_success,
    users_failed,
    groups_total,
    groups_success,
    groups_failed,
):

    report = (
        "✅ <b>ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>\n\n"

        "👤 <b>ᴜsᴇʀs</b>\n"
        f"• ᴛᴏᴛᴀʟ : <code>{users_total}</code>\n"
        f"• sᴜᴄᴄᴇss : <code>{users_success}</code>\n"
        f"• ғᴀɪʟᴇᴅ : <code>{users_failed}</code>\n\n"

        "👥 <b>ɢʀᴏᴜᴘs</b>\n"
        f"• ᴛᴏᴛᴀʟ : <code>{groups_total}</code>\n"
        f"• sᴜᴄᴄᴇss : <code>{groups_success}</code>\n"
        f"• ғᴀɪʟᴇᴅ : <code>{groups_failed}</code>\n\n"

        "📊 <b>ᴏᴠᴇʀᴀʟʟ</b>\n"
        f"• ᴛᴏᴛᴀʟ : <code>{users_total + groups_total}</code>\n"
        f"• sᴜᴄᴄᴇss : <code>{users_success + groups_success}</code>\n"
        f"• ғᴀɪʟᴇᴅ : <code>{users_failed + groups_failed}</code>"
    )

    try:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=report,
            parse_mode="HTML",
        )
    except Exception:
        pass

    return report

# ============================================================
# /bc (Copy Broadcast)
# ============================================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ."
        )

    msg = update.message.reply_to_message

    users = await get_all_users()
    groups = await get_all_groups()

    # Runtime deduplication (does NOT alter database)
    users = list(dict.fromkeys(users))
    groups = list(dict.fromkeys(groups))

    users_total = len(users)
    groups_total = len(groups)

    users_success = 0
    users_failed = 0

    groups_success = 0
    groups_failed = 0

    total = users_total + groups_total
    processed = 0

    status = await update.message.reply_text(
        f"🚀 ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀʀᴛᴇᴅ...\n\n"
        f"📤 ᴛᴏᴛᴀʟ ᴄʜᴀᴛs : {total}"
    )

    # ---------------- USERS ---------------- #

    for user_id in users:

        ok = await _copy_message(
            context=context,
            msg=msg,
            chat_id=user_id,
            pin=False,      # Bots can't pin in private chats
        )

        if ok:
            users_success += 1
        else:
            users_failed += 1

        processed += 1

        if processed % 25 == 0:
            try:
                await status.edit_text(
                    "🚀 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...\n\n"
                    f"ᴘʀᴏᴄᴇssᴇᴅ : {processed}/{total}\n"
                    f"ᴜsᴇʀs : {users_success}/{users_total}\n"
                    f"ɢʀᴏᴜᴘs : {groups_success}/{groups_total}"
                )
            except Exception:
                pass

    # ---------------- GROUPS ---------------- #

    for group_id in groups:

        ok = await _copy_message(
            context=context,
            msg=msg,
            chat_id=group_id,
            pin=True,
        )

        if ok:
            groups_success += 1
        else:
            groups_failed += 1

        processed += 1

        if processed % 25 == 0:
            try:
                await status.edit_text(
                    "🚀 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...\n\n"
                    f"ᴘʀᴏᴄᴇssᴇᴅ : {processed}/{total}\n"
                    f"ᴜsᴇʀs : {users_success}/{users_total}\n"
                    f"ɢʀᴏᴜᴘs : {groups_success}/{groups_total}"
                )
            except Exception:
                pass

    report = await _send_report(
        update=update,
        context=context,
        users_total=users_total,
        users_success=users_success,
        users_failed=users_failed,
        groups_total=groups_total,
        groups_success=groups_success,
        groups_failed=groups_failed,
    )

    try:
        await status.edit_text(
            report,
            parse_mode="HTML",
        )
    except Exception:
        pass

# ============================================================
# /fbc (Forward Broadcast)
# ============================================================

async def forward_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    if not update.message.reply_to_message:
        return await update.message.reply_text(
            "❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ғᴏʀᴡᴀʀᴅ ʙʀᴏᴀᴅᴄᴀsᴛ."
        )

    msg = update.message.reply_to_message

    users = await get_all_users()
    groups = await get_all_groups()

    # Runtime deduplication
    users = list(dict.fromkeys(users))
    groups = list(dict.fromkeys(groups))

    users_total = len(users)
    groups_total = len(groups)

    users_success = 0
    users_failed = 0

    groups_success = 0
    groups_failed = 0

    total = users_total + groups_total
    processed = 0

    status = await update.message.reply_text(
        f"🚀 ғᴏʀᴡᴀʀᴅ ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀʀᴛᴇᴅ...\n\n"
        f"📤 ᴛᴏᴛᴀʟ ᴄʜᴀᴛs : {total}"
    )

    # ---------------- USERS ---------------- #

    for user_id in users:

        ok = await _forward_message(
            context=context,
            msg=msg,
            chat_id=user_id,
            pin=False,
        )

        if ok:
            users_success += 1
        else:
            users_failed += 1

        processed += 1

        if processed % 25 == 0:
            try:
                await status.edit_text(
                    "🚀 ғᴏʀᴡᴀʀᴅ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...\n\n"
                    f"ᴘʀᴏᴄᴇssᴇᴅ : {processed}/{total}\n"
                    f"ᴜsᴇʀs : {users_success}/{users_total}\n"
                    f"ɢʀᴏᴜᴘs : {groups_success}/{groups_total}"
                )
            except Exception:
                pass

    # ---------------- GROUPS ---------------- #

    for group_id in groups:

        ok = await _forward_message(
            context=context,
            msg=msg,
            chat_id=group_id,
            pin=True,
        )

        if ok:
            groups_success += 1
        else:
            groups_failed += 1

        processed += 1

        if processed % 25 == 0:
            try:
                await status.edit_text(
                    "🚀 ғᴏʀᴡᴀʀᴅ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...\n\n"
                    f"ᴘʀᴏᴄᴇssᴇᴅ : {processed}/{total}\n"
                    f"ᴜsᴇʀs : {users_success}/{users_total}\n"
                    f"ɢʀᴏᴜᴘs : {groups_success}/{groups_total}"
                )
            except Exception:
                pass

    report = await _send_report(
        update=update,
        context=context,
        users_total=users_total,
        users_success=users_success,
        users_failed=users_failed,
        groups_total=groups_total,
        groups_success=groups_success,
        groups_failed=groups_failed,
    )

    try:
        await status.edit_text(
            report,
            parse_mode="HTML",
        )
    except Exception:
        pass

# ============================================================
# BULK ADD USERS / GROUPS
# ============================================================

async def bulk_add(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    if not context.args:
        return await update.message.reply_text(
            "❌ ᴜsᴀɢᴇ:\n"
            "/bulkadd user 12345 67890\n"
            "/bulkadd group -1001234567890 -1009876543210"
        )

    mode = context.args[0].lower()
    ids = context.args[1:]

    if not ids:
        return await update.message.reply_text("❌ ɴᴏ ɪᴅs ᴘʀᴏᴠɪᴅᴇᴅ.")

    success = 0
    failed = 0

    for chat in ids:
        try:
            chat_id = int(chat)

            if mode == "user":
                if not await users_col.find_one({"_id": chat_id}):
                    await users_col.insert_one({"_id": chat_id})

            elif mode == "group":
                if not await groups_col.find_one({"_id": chat_id}):
                    await groups_col.insert_one({"_id": chat_id})

            else:
                return await update.message.reply_text(
                    "❌ ᴍᴏᴅᴇ ᴍᴜsᴛ ʙᴇ ᴇɪᴛʜᴇʀ 'ᴜsᴇʀ' ᴏʀ 'ɢʀᴏᴜᴘ'."
                )

            success += 1

        except Exception:
            failed += 1

    await update.message.reply_text(
        "✅ ʙᴜʟᴋ ᴀᴅᴅ ᴄᴏᴍᴘʟᴇᴛᴇᴅ\n\n"
        f"✔ sᴜᴄᴄᴇssғᴜʟʟʏ ᴀᴅᴅᴇᴅ : {success}\n"
        f"❌ ғᴀɪʟᴇᴅ : {failed}"
    )


# ============================================================
# /stick — START STICKER
# ============================================================

async def set_start_sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Owner / Sudo authorization
    if not await require_sudo(update, context):
        return

    message = update.effective_message

    if not message:
        return

    args = context.args or []

    # -------- /stick reset --------
    if args and args[0].lower() == "reset":
        try:
            await clear_start_sticker()
            return await message.reply_text(
                "♻️ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ ʀᴇsᴇᴛ"
            )
        except Exception as e:
            print(f"[STICK] Clear failed: {e}")
            return await message.reply_text(
                "❌ ғᴀɪʟᴇᴅ ᴛᴏ ʀᴇsᴇᴛ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ."
            )

    # -------- /stick <sticker_id> --------
    if args:
        sticker_id = args[0].strip()

        if not sticker_id:
            return await message.reply_text(
                "❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ sᴛɪᴄᴋᴇʀ ᴏʀ ᴜsᴇ:\n"
                "/stick <sᴛɪᴄᴋᴇʀ_ɪᴅ>"
            )

        try:
            saved = await set_start_sticker(sticker_id)

            if not saved:
                return await message.reply_text(
                    "❌ ɪɴᴠᴀʟɪᴅ sᴛɪᴄᴋᴇʀ ɪᴅ."
                )

            return await message.reply_text(
                "✅ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ ᴜᴘᴅᴀᴛᴇᴅ"
            )
        except Exception as e:
            print(f"[STICK] Save failed: {e}")
            return await message.reply_text(
                "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴜᴘᴅᴀᴛᴇ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ."
            )

    # -------- /stick (reply to sticker) --------
    replied = message.reply_to_message

    if not replied or not replied.sticker:
        return await message.reply_text(
            "❌ ʀᴇᴘʟʏ ᴛᴏ ᴀ sᴛɪᴄᴋᴇʀ ᴏʀ ᴜsᴇ:\n"
            "/stick <sᴛɪᴄᴋᴇʀ_ɪᴅ>"
        )

    sticker_id = replied.sticker.file_id

    try:
        saved = await set_start_sticker(sticker_id)

        if not saved:
            return await message.reply_text(
                "❌ ɪɴᴠᴀʟɪᴅ sᴛɪᴄᴋᴇʀ ɪᴅ."
            )

        return await message.reply_text(
            "✅ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ ᴜᴘᴅᴀᴛᴇᴅ"
        )
    except Exception as e:
        print(f"[STICK] Save failed: {e}")
        return await message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴜᴘᴅᴀᴛᴇ sᴛᴀʀᴛ sᴛɪᴄᴋᴇʀ."
        )

# ============================================================
# PROMOTIONAL CHANNELS (FORCE-SUB) — ADMIN COMMANDS
# ============================================================

async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    text = update.message.text.replace("/addchannel", "", 1).strip()

    parts = [p.strip() for p in text.split("|")]

    if len(parts) != 3:
        return await update.message.reply_text(
            "❌ ᴜsᴀɢᴇ:\n"
            "/addchannel Name | Channel ID | Channel Link\n\n"
            "ᴇxᴀᴍᴘʟᴇ:\n"
            "/addchannel Anime Promo | -1009876543210 | https://t.me/animepromo"
        )

    name, raw_id, link = parts

    if not name or not raw_id or not link:
        return await update.message.reply_text(
            "❌ ᴀʟʟ ᴛʜʀᴇᴇ ғɪᴇʟᴅs ᴀʀᴇ ʀᴇǫᴜɪʀᴇᴅ."
        )

    try:
        channel_id = int(raw_id)
    except ValueError:
        return await update.message.reply_text(
            "❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ.\n"
            "ᴜsᴇ ᴀ ɴᴜᴍᴇʀɪᴄ ɪᴅ ʟɪᴋᴇ -1001234567890"
        )

    try:
        exists = await channel_exists(channel_id)
        if exists:
            return await update.message.reply_text(
                f"⚠️ ᴄʜᴀɴɴᴇʟ ᴀʟʀᴇᴀᴅʏ ᴇxɪsᴛs:\n<code>{channel_id}</code>",
                parse_mode="HTML",
            )

        ok = await add_promotional_channel(
            name=name,
            channel_id=channel_id,
            channel_link=link,
        )

        if not ok:
            return await update.message.reply_text(
                "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ."
            )

        await update.message.reply_text(
            "✅ ᴘʀᴏᴍᴏᴛɪᴏɴᴀʟ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ\n\n"
            f"📢 ɴᴀᴍᴇ: {name}\n"
            f"🆔 ɪᴅ: <code>{channel_id}</code>\n"
            f"🔗 ʟɪɴᴋ: {link}",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[ADDCHANNEL] Failed: {e}")
        await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ."
        )


async def delchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    if not context.args:
        return await update.message.reply_text(
            "❌ ᴜsᴀɢᴇ:\n/delchannel <channel_id>"
        )

    try:
        channel_id = int(context.args[0].strip())
    except ValueError:
        return await update.message.reply_text(
            "❌ ɪɴᴠᴀʟɪᴅ ᴄʜᴀɴɴᴇʟ ɪᴅ."
        )

    try:
        removed = await remove_promotional_channel(channel_id)

        if removed:
            await update.message.reply_text(
                f"✅ ᴄʜᴀɴɴᴇʟ ʀᴇᴍᴏᴠᴇᴅ:\n<code>{channel_id}</code>",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "❌ ᴄʜᴀɴɴᴇʟ ɴᴏᴛ ғᴏᴜɴᴅ."
            )
    except Exception as e:
        print(f"[DELCHANNEL] Failed: {e}")
        await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ."
        )


async def channels(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_sudo(update, context):
        return

    try:
        promos = await get_promotional_channels(active_only=True)
    except Exception as e:
        print(f"[CHANNELS] Failed: {e}")
        return await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ ᴄʜᴀɴɴᴇʟs."
        )

    if not promos:
        return await update.message.reply_text(
            "📭 ɴᴏ ᴀᴄᴛɪᴠᴇ ᴘʀᴏᴍᴏᴛɪᴏɴᴀʟ ᴄʜᴀɴɴᴇʟs."
        )

    text = "📢 ᴀᴄᴛɪᴠᴇ ᴘʀᴏᴍᴏᴛɪᴏɴᴀʟ ᴄʜᴀɴɴᴇʟs\n\n"

    for i, promo in enumerate(promos, start=1):
        text += (
            f"{i}. {promo.get('name', 'Unnamed')}\n"
            f"🆔 <code>{promo.get('channel_id')}</code>\n"
            f"🔗 {promo.get('channel_link', '')}\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# ============================================================
# SUDO MANAGEMENT (OWNER-ONLY)
# ============================================================

def _extract_target_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Resolve the target user ID for sudo management.

    Priority:
        1. Reply to a message → use the replied user's ID
        2. context.args[0]    → parse as int

    Returns (user_id: int | None, error: str | None)
    """
    reply = getattr(update.message, "reply_to_message", None)
    if reply is not None:
        replied_user = getattr(reply, "from_user", None)
        if replied_user is None:
            return None, (
                "❌ ᴄᴏᴜʟᴅ ɴᴏᴛ ʀᴇᴀᴅ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ."
            )
        try:
            return int(replied_user.id), None
        except (TypeError, ValueError):
            return None, "❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ."

    if not context.args:
        return None, None

    try:
        return int(context.args[0]), None
    except (TypeError, ValueError):
        return None, "❌ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ."


async def _resolve_profile(context, user_id: int):
    """
    Best-effort Telegram profile lookup.

    Returns a dict with keys:
        display_name, username, user_id, profile_url
    Always returns something usable — never raises.
    """
    display_name = "Unknown User"
    username = None

    try:
        chat = await context.bot.get_chat(user_id)

        first = getattr(chat, "first_name", "") or ""
        last = getattr(chat, "last_name", "") or ""
        full = (first + " " + last).strip()

        if full:
            display_name = full

        uname = getattr(chat, "username", None)
        if uname:
            username = uname
    except Exception:
        pass

    return {
        "display_name": display_name,
        "username": username,
        "user_id": user_id,
        "profile_url": f"tg://user?id={user_id}",
    }


def _render_profile_block(profile: dict) -> str:
    """
    Build the shared profile HTML block used across sudo commands.
    All dynamic text is HTML-escaped.
    """
    uid = profile["user_id"]
    url = profile["profile_url"]

    safe_name = escape(profile["display_name"] or "Unknown User")

    if profile["username"]:
        username_line = f"@{escape(profile['username'])}"
    else:
        username_line = "<i>Not Set</i>"

    return (
        f"👤 <b>ɴᴀᴍᴇ:</b> "
        f"<a href=\"{url}\">{safe_name}</a>\n"
        f"🔹 <b>ᴜsᴇʀɴᴀᴍᴇ:</b> {username_line}\n"
        f"🆔 <b>ᴜsᴇʀ ɪᴅ:</b> <code>{uid}</code>\n"
        f"🔗 <b>ᴘʀᴏғɪʟᴇ:</b> "
        f"<a href=\"{url}\">ᴏᴘᴇɴ ᴘʀᴏғɪʟᴇ</a>"
    )


async def add_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_owner(update, context):
        return

    target_user_id, error = _extract_target_user_id(update, context)

    if error:
        return await update.message.reply_text(error)

    if target_user_id is None:
        return await update.message.reply_text(
            "❌ <b>ɪɴᴠᴀʟɪᴅ ᴜsᴀɢᴇ</b>\n\n"
            "ᴜsᴇ:\n"
            "<code>/addsudo &lt;ᴜsᴇʀ_ɪᴅ&gt;</code>\n\n"
            "ᴇxᴀᴍᴘʟᴇ:\n"
            "<code>/addsudo 8055084559</code>\n\n"
            "ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴡɪᴛʜ <code>/addsudo</code>.",
            parse_mode="HTML",
        )

    # Owner protection
    if target_user_id == OWNER_ID:
        return await update.message.reply_text(
            "👑 <b>ᴏᴡɴᴇʀ ᴀᴄᴄᴏᴜɴᴛ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🛡️ ᴛʜɪs ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.\n\n"
            f"🆔 <b>ᴜsᴇʀ ɪᴅ:</b> <code>{OWNER_ID}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>ᴏᴡɴᴇʀ ᴄᴀɴɴᴏᴛ ʙᴇ ᴀᴅᴅᴇᴅ ᴀs sᴜᴅᴏ.</i>",
            parse_mode="HTML",
        )

    profile = await _resolve_profile(context, target_user_id)
    profile_block = _render_profile_block(profile)

    try:
        already_sudo = await is_sudo_user(target_user_id)
        if already_sudo:
            return await update.message.reply_text(
                "🛡️ <b>sᴜᴅᴏ ᴀʟʀᴇᴀᴅʏ ᴇxɪsᴛs</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"{profile_block}\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "⚠️ <i>ᴛʜɪs ᴜsᴇʀ ɪs ᴀʟʀᴇᴀᴅʏ ᴀ sᴜᴅᴏ.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

        ok = await add_sudo_user(target_user_id, update.effective_user.id)
        if not ok:
            return await update.message.reply_text(
                "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴅᴅ sᴜᴅᴏ ᴜsᴇʀ."
            )

        await update.message.reply_text(
            "🛡️ <b>sᴜᴅᴏ ᴀᴅᴅᴇᴅ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{profile_block}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>sᴛᴀᴛᴜs:</b> sᴜᴅᴏ ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ.",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[ADDSUDO] Failed: {e}")
        await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴜᴘᴅᴀᴛᴇ sᴜᴅᴏ ᴜsᴇʀ."
        )


async def del_sudo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_owner(update, context):
        return

    target_user_id, error = _extract_target_user_id(update, context)

    if error:
        return await update.message.reply_text(error)

    if target_user_id is None:
        return await update.message.reply_text(
            "❌ <b>ɪɴᴠᴀʟɪᴅ ᴜsᴀɢᴇ</b>\n\n"
            "ᴜsᴇ:\n"
            "<code>/delsudo &lt;ᴜsᴇʀ_ɪᴅ&gt;</code>\n\n"
            "ᴇxᴀᴍᴘʟᴇ:\n"
            "<code>/delsudo 8055084559</code>\n\n"
            "ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴡɪᴛʜ <code>/delsudo</code>.",
            parse_mode="HTML",
        )

    # Owner protection
    if target_user_id == OWNER_ID:
        return await update.message.reply_text(
            "👑 <b>ᴏᴡɴᴇʀ ᴀᴄᴄᴏᴜɴᴛ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🛡️ ᴛʜɪs ᴀᴄᴄᴏᴜɴᴛ ɪs ᴛʜᴇ ʙᴏᴛ ᴏᴡɴᴇʀ.\n\n"
            f"🆔 <b>ᴜsᴇʀ ɪᴅ:</b> <code>{OWNER_ID}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>ᴏᴡɴᴇʀ ᴄᴀɴɴᴏᴛ ʙᴇ ʀᴇᴍᴏᴠᴇᴅ ᴀs sᴜᴅᴏ.</i>",
            parse_mode="HTML",
        )

    profile = await _resolve_profile(context, target_user_id)
    profile_block = _render_profile_block(profile)

    try:
        already_sudo = await is_sudo_user(target_user_id)
        if not already_sudo:
            return await update.message.reply_text(
                "❌ <b>sᴜᴅᴏ ɴᴏᴛ ғᴏᴜɴᴅ</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"{profile_block}\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "⚠️ <i>ᴛʜɪs ᴜsᴇʀ ɪs ɴᴏᴛ ᴀ sᴜᴅᴏ.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

        ok = await remove_sudo_user(target_user_id)
        if not ok:
            return await update.message.reply_text(
                "❌ ғᴀɪʟᴇᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ sᴜᴅᴏ ᴜsᴇʀ."
            )

        await update.message.reply_text(
            "🗑️ <b>sᴜᴅᴏ ʀᴇᴍᴏᴠᴇᴅ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{profile_block}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>sᴛᴀᴛᴜs:</b> sᴜᴅᴏ ᴀᴄᴄᴇss ʀᴇᴍᴏᴠᴇᴅ.",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        print(f"[DELSUDO] Failed: {e}")
        await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ᴜᴘᴅᴀᴛᴇ sᴜᴅᴏ ᴜsᴇʀ."
        )


async def sudo_list(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_owner(update, context):
        return

    try:
        sudo_users = await get_all_sudo_users()
        total = await total_sudo_users()
    except Exception as e:
        print(f"[SUDOLIST] Failed: {e}")
        return await update.message.reply_text(
            "❌ ғᴀɪʟᴇᴅ ᴛᴏ ʟᴏᴀᴅ sᴜᴅᴏ ᴜsᴇʀs."
        )

    if not sudo_users:
        return await update.message.reply_text(
            "📭 ɴᴏ sᴜᴅᴏ ᴜsᴇʀs ғᴏᴜɴᴅ."
        )

    text = "🛡️ <b>sᴜᴅᴏ ᴜsᴇʀs</b>\n\n"

    for i, user_id in enumerate(sudo_users, start=1):
        text += f"{i}. <code>{user_id}</code>\n"

    text += f"\n📊 ᴛᴏᴛᴀʟ: {total}"

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
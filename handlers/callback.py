# ==============================
# CALLBACK HANDLER
# ==============================

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import ContextTypes

from telegram.error import BadRequest

from config import (
    ANIME_PER_PAGE,
    FORCE_CHANNEL,
)

from handlers.animelist import build_page

from database.mongo import (
    get_all_anime,
    get_all_groups,
    total_groups,
    remove_group,

    # Request System
    get_request,
    update_request_status,
    update_request_reply,
)

# ==========================================
# GLOBAL VARIABLES
# ==========================================

# Stores pending admin replies
pending_replies = {}

# ==========================================
# GROUPS PAGINATION
# ==========================================

async def groups_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if not query.data.startswith("groups_"):
        return

    page = int(query.data.split("_")[1])

    PER_PAGE = 5

    all_groups = await get_all_groups()
    total = await total_groups()

    start = page * PER_PAGE
    end = start + PER_PAGE

    text = (
        f"🏘 <b>ᴛᴏᴛᴀʟ ɢʀᴏᴜᴘs :</b> {total}\n"
        f"📄 <b>ᴘᴀɢᴇ :</b> {page + 1}\n\n"
    )

    for group in all_groups[start:end]:

        chat_id = group["_id"]

        try:

            chat = await context.bot.get_chat(chat_id)

            members = await context.bot.get_chat_member_count(chat_id)

            me = await context.bot.get_chat_member(
                chat_id,
                context.bot.id,
            )

            status = (
                "👑 ᴀᴅᴍɪɴ"
                if me.status == "administrator"
                else "👤 ᴍᴇᴍʙᴇʀ"
            )

            try:
                invite = (
                    chat.invite_link
                    if me.status == "administrator"
                    else "ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ"
                )
            except Exception:
                invite = "ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ"

            text += (
                f"📌 <b>{chat.title}</b>\n"
                f"🆔 <code>{chat.id}</code>\n"
                f"👥 {members} ᴍᴇᴍʙᴇʀs\n"
                f"🤖 {status}\n"
                f"🔗 {invite}\n\n"
            )

        except Exception:

            await remove_group(chat_id)

    buttons = []

    row = []

    if page > 0:
        row.append(
            InlineKeyboardButton(
                "⬅ Previous",
                callback_data=f"groups_{page-1}",
                style="primary",
            )
        )

    if end < len(all_groups):
        row.append(
            InlineKeyboardButton(
                "➡ Next",
                callback_data=f"groups_{page+1}",
                style="primary",
            )
        )

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data=f"groups_{page}",
                style="primary",
            )
        ]
    )

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons),
    )

# ==========================================
# BUTTON BUILDER
# ==========================================

def build_buttons(anime):

    keyboard = []

    hindi = anime.get("hindi_link", "-")
    english = anime.get("english_link", "-")
    old_link = anime.get("link", "-")  # Backward compatibility

    # ------------------------------
    # Hindi Button
    # ------------------------------
    if hindi and hindi != "-":
        keyboard.append(
            [
                InlineKeyboardButton(
                    "𝖶𝖺𝗍𝖼𝗁 𝖨𝗇 𝖧𝗂𝗇𝖽𝗂 𝖣𝗎𝖻",
                    url=hindi,
                    style="success",
                )
            ]
        )

    # ------------------------------
    # English Button
    # ------------------------------
    if english and english != "-":
        keyboard.append(
            [
                InlineKeyboardButton(
                    "𝖶𝖺𝗍𝖼𝗁 𝖨𝗇 𝖩𝖺𝗉/𝖤𝗇𝗀𝗅𝗂𝗌𝗁",
                    url=english,
                    style="success",
                )
            ]
        )

    # ------------------------------
    # Old Database Support
    # ------------------------------
    if (
        (not hindi or hindi == "-")
        and (not english or english == "-")
        and old_link
        and old_link != "-"
    ):
        keyboard.append(
            [
                InlineKeyboardButton(
                    "𝗪𝗮𝘁𝗰𝗵 & 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱",
                    url=old_link,
                    style="success",
                )
            ]
        )

    # ------------------------------
    # Join Main Channel
    # ------------------------------
    keyboard.append(
        [
            InlineKeyboardButton(
                "𝖩𝗈𝗂𝗇 𝖬𝖺𝗂𝗇 𝖢𝗁𝖺𝗇𝗇𝖾",
                url=f"https://t.me/{FORCE_CHANNEL.replace('@', '')}",
                style="success",
            )
        ]
    )

    return InlineKeyboardMarkup(keyboard)

# ==========================================
# CALLBACK HANDLER
# ==========================================

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""

    animes = await get_all_anime()

    # ==========================================
    # ANIME CALLBACK
    # ==========================================

    if data.startswith("anime_"):

        anime_name = data.replace("anime_", "").lower()

        anime_data = None

        for anime in animes:

            if anime["name"].lower() == anime_name:
                anime_data = anime
                break

        if not anime_data:

            await query.answer(
                "ᴀɴɪᴍᴇ ɴᴏᴛ ғᴏᴜɴᴅ.",
                show_alert=True,
            )
            return

        try:

            await query.message.reply_sticker(
                sticker=anime_data["sticker"],
                reply_markup=build_buttons(anime_data),
            )

        except Exception:

            await query.message.reply_text(
                anime_data["name"],
                reply_markup=build_buttons(anime_data),
            )

        return

    # ==========================================
    # REQUEST CALLBACKS
    # ==========================================

    elif data.startswith("req_"):

        action, req_id = data.split(":", 1)

        req = await get_request(req_id)

        if not req:
            await query.answer(
                "❌ ʀᴇǫᴜᴇsᴛ ɴᴏᴛ ғᴏᴜɴᴅ.",
                show_alert=True,
            )
            return

        # -----------------------------
        # Reply Button
        # -----------------------------
        if action == "req_reply":

            pending_replies[query.from_user.id] = req_id

            await query.message.reply_text(
                "📝 sᴇɴᴅ ʏᴏᴜʀ ʀᴇᴘʟʏ ᴛᴏ ᴛʜɪs ʀᴇǫᴜᴇsᴛ.\n\n"
                "ᴜsᴇ /cancelreply ᴛᴏ ᴄᴀɴᴄᴇʟ."
            )

            await query.answer()

            return

        # -----------------------------
        # Status Buttons
        # -----------------------------
        status_map = {
            "req_added": (
                "ᴀᴅᴅᴇᴅ ✅",
                "🎉 ɢʀᴇᴀᴛ ɴᴇᴡs!\n\n"
                "ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛᴇᴅ ᴀɴɪᴍᴇ ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ.\n\n"
                f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ : {req_id}"
            ),

            "req_working": (
                "ᴡᴏʀᴋɪɴɢ 🔄",
                "🛠 ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴘʀᴏᴄᴇss.\n\n"
                f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ : {req_id}"
            ),

            "req_denied": (
                "ɴᴏᴛ ᴘᴏssɪʙʟᴇ ❌",
                "😔 sᴏʀʀʏ.\n\n"
                "ᴄᴜʀʀᴇɴᴛʟʏ ᴡᴇ ᴄᴀɴɴᴏᴛ ᴘʀᴏᴠɪᴅᴇ ᴛʜɪs ᴀɴɪᴍᴇ.\n\n"
                f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ : {req_id}"
            ),

            "req_close": (
                "ᴄʟᴏsᴇᴅ 🔒",
                "✅ ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ ᴄʟᴏsᴇᴅ.\n\n"
                f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ : {req_id}"
            ),
        }

        if action not in status_map:
            return

        status, user_message = status_map[action]

        await update_request_status(
            req_id,
            status,
        )

        try:
            await context.bot.send_message(
                chat_id=req["user_id"],
                text=user_message,
            )
        except Exception:
            pass

        text = query.message.text_html

        if text and "🟢 <b>sᴛᴀᴛᴜs:</b>" in text:
            text = text.split("🟢 <b>sᴛᴀᴛᴜs:</b>")[0]

        if text and "🟡 <b>sᴛᴀᴛᴜs:</b>" in text:
            text = text.split("🟡 <b>sᴛᴀᴛᴜs:</b>")[0]

        text += f"\n\n🟢 <b>sᴛᴀᴛᴜs:</b> {status}"

        try:
            await query.edit_message_text(
                text=text,
                parse_mode="HTML",
                reply_markup=query.message.reply_markup,
            )
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

        await query.answer(
            f"sᴛᴀᴛᴜs ᴜᴘᴅᴀᴛᴇᴅ ᴛᴏ {status}"
        )

        return

    # ==========================================
    # IGNORE BUTTON
    # ==========================================

    elif data == "ignore":

        await query.answer(
            "ᴜsᴇ ᴘʀᴇᴠɪᴏᴜs / ɴᴇxᴛ ʙᴜᴛᴛᴏɴs ᴏɴʟʏ.",
            show_alert=False,
        )

        return

    # ==========================================
    # ANIME LIST PAGINATION
    # ==========================================

    elif data.startswith("alist_"):

        page = int(data.split("_")[1])

        animes = sorted(
            animes,
            key=lambda x: x["name"].lower()
        )

        page_data, page, total_pages = build_page(
            animes,
            page
        )

        text = (
            "📚 <b>ᴀɴɪᴍᴇ ᴄᴏʟʟᴇᴄᴛɪᴏɴ</b>\n\n"
            "╭━━━━━━━━━━━━━━━━━━╮\n"
            f"📄 <b>ᴘᴀɢᴇ :</b> {page}/{total_pages}\n"
            f"🎬 <b>ᴛᴏᴛᴀʟ :</b> {len(animes)} ᴀɴɪᴍᴇ\n"
            "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        )

        start_no = (page - 1) * ANIME_PER_PAGE

        for i, anime in enumerate(
            page_data,
            start=start_no + 1
        ):

            hindi = anime.get("hindi_link", "-")
            english = anime.get("english_link", "-")
            old = anime.get("link", "-")

            text += f"<b>{i}. {anime['name']}</b>\n"
            text += "➥ "

            links = []

            if hindi and hindi != "-":
                links.append(
                    f"<a href='{hindi}'>𝗛𝗶𝗻𝗱𝗶 𝗗𝘂𝗯</a>"
                )

            if english and english != "-":
                links.append(
                    f"<a href='{english}'>𝗝𝗮𝗽𝗲𝗻𝘀𝗲/𝗘𝗻𝗴𝗹𝗶𝘀𝗵</a>"
                )

            if old and old != "-" and not links:
                links.append(
                    f"<a href='{old}'>🎬 Watch</a>"
                )

            if links:
                text += " | ".join(links)
            else:
                text += "❌ ɴᴏ ʟɪɴᴋ"

            text += "\n\n"

        prev_page = page - 1 if page > 1 else 1
        next_page = page + 1 if page < total_pages else total_pages

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⏪ Previous",
                        callback_data=f"alist_{prev_page}",
                        style="primary",
                    ),
                    InlineKeyboardButton(
                        f"📄 {page}/{total_pages}",
                        callback_data="ignore",
                        style="primary",
                    ),
                    InlineKeyboardButton(
                        "Next ⏩",
                        callback_data=f"alist_{next_page}",
                        style="primary",
                    ),
                ]
            ]
        )

        # ==========================================
        # PHOTO vs TEXT SAFE EDIT
        # ==========================================

        try:
            if query.message and query.message.photo:
                await query.edit_message_caption(
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            else:
                await query.edit_message_text(
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=keyboard,
                )

        except BadRequest as e:

            if "Message is not modified" not in str(e):
                raise

        return

    # ==========================================
    # UNKNOWN CALLBACK
    # ==========================================

    else:

        await query.answer(
            "ᴜɴᴋɴᴏᴡɴ ʙᴜᴛᴛᴏɴ.",
            show_alert=False,
        )

        return

# ==========================================
# ADMIN CUSTOM REPLY
# ==========================================

async def admin_request_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if user_id not in pending_replies:
        return

    req_id = pending_replies.pop(user_id)

    req = await get_request(req_id)

    if not req:
        await update.message.reply_text("❌ ʀᴇǫᴜᴇsᴛ ɴᴏᴛ ғᴏᴜɴᴅ.")
        return

    reply = update.message.text

    await update_request_reply(req_id, reply)

    try:
        await context.bot.send_message(
            chat_id=req["user_id"],
            text=(
                "📩 **ʀᴇᴘʟʏ ғʀᴏᴍ ᴀᴅᴍɪɴ**\n\n"
                f"{reply}\n\n"
                f"🆔 ʀᴇǫᴜᴇsᴛ ɪᴅ: `{req_id}`"
            ),
            parse_mode="Markdown",
        )

    except Exception:
        await update.message.reply_text(
            "⚠️ ᴜsᴇʀ ʜᴀs ʙʟᴏᴄᴋᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴏʀ ᴄᴀɴɴᴏᴛ ʙᴇ ʀᴇᴀᴄʜᴇᴅ."
        )
        return

    await update.message.reply_text(
        "✅ ʀᴇᴘʟʏ sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ."
    )

# ==========================================
# CANCEL ADMIN REPLY
# ==========================================

async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    pending_replies.pop(update.effective_user.id, None)

    await update.message.reply_text(
        "❌ ʀᴇᴘʟʏ ᴄᴀɴᴄᴇʟʟᴇᴅ."
    )
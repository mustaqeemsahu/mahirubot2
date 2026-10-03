# ==============================
# MAIN BOT FILE
# LOCAL POLLING + RENDER WEBHOOK
# ==============================

import os
import logging

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    InlineQueryHandler,
    ConversationHandler,
    filters,
)

# Config
from config import BOT_TOKEN

# Database
from database.mongo import create_indexes, load_anime_cache

# Handlers
from handlers.start import start
from handlers.anime import anime_search, add_anime, del_anime
from handlers.search import improved_anime, button_search
from handlers.animelist import animelist
from handlers.group import (
    chat_member_update,
    welcome_new_members,
    track_group_message,
)
from handlers.callback import button_click, groups_callback, admin_request_reply, cancel_reply
from handlers.inline import inline_query
from handlers.admin import (
    stats,
    broadcast,
    bulk_add,
    forward_broadcast,
    uptime,
    groups,
    set_start_sticker_cmd,
    addchannel,
    delchannel,
    channels,
    add_sudo,
    del_sudo,
    sudo_list,
)
from handlers.channel_logger import channel_member_update
from handlers.request import (
    request_start, anime_name, language_callback, dub_callback,
    season, extra, skip_season, skip_extra, cancel_request,
    ANIME, LANGUAGE, DUB, SEASON, EXTRA
)
from handlers.misc import (
    help_cmd,
    id_command,
    owner_command,
    adminlist_command,
    roast_user,
)
from handlers.system import (
    mahiru_ping,
    is_mahiru_ping,
    bstats,
    banall,
    restart,
)


# ==============================
# LOGGING
# ==============================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


# ==============================
# DATABASE INIT
# ==============================
async def post_init(application):
    try:
        await create_indexes()
        await load_anime_cache()
        print("✅ Database Connected")
    except Exception as e:
        print(f"⚠️ Database Error: {e}")


# ==============================
# MAIN FUNCTION
# ==============================
def main():

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )


    # ==========================
    # CONVERSATION HANDLER
    # ==========================
    request_handler = ConversationHandler(
        entry_points=[
            CommandHandler("request", request_start)
        ],

        states={
            ANIME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    anime_name
                )
            ],

            LANGUAGE: [
                CallbackQueryHandler(
                    language_callback,
                    pattern="^lang_"
                )
            ],

            DUB: [
                CallbackQueryHandler(
                    dub_callback,
                    pattern="^dub_"
                )
            ],

            SEASON: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    season
                ),
                CommandHandler("skip", skip_season),
            ],

            EXTRA: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    extra
                ),
                CommandHandler("skip", skip_extra),
            ],
        },

        fallbacks=[
            CommandHandler("cancel", cancel_request)
        ],

        allow_reentry=True,
    )


    # ==========================================
    # HIGH-PRIORITY TEXT TRIGGER: "mahiru ping"
    # ==========================================
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND
            & filters.Regex(r"(?i)^\s*mahiru\s+ping\s*$"),
            mahiru_ping,
        ),
        group=-1,
    )


    # ==========================================
    # GROUP MEMBER TRACKER (any group message)
    # ==========================================
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION | filters.ATTACHMENT),
            track_group_message,
        ),
        group=-1,
    )


    # ==========================
    # USER COMMANDS
    # ==========================
    app.add_handler(request_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("anime", anime_search))
    app.add_handler(CommandHandler("search", improved_anime))
    app.add_handler(CommandHandler("btn", button_search))
    app.add_handler(CommandHandler("animelist", animelist))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("owner", owner_command))
    app.add_handler(CommandHandler("adminlist", adminlist_command))
    app.add_handler(CommandHandler("admins", adminlist_command))
    app.add_handler(CommandHandler("roast", roast_user))


    # ==========================
    # SYSTEM COMMANDS
    # ==========================
    app.add_handler(CommandHandler("bstats", bstats))
    app.add_handler(CommandHandler("banall", banall))
    app.add_handler(CommandHandler("restart", restart))


    # ==========================
    # ADMIN COMMANDS (Owner + Sudo)
    # ==========================
    app.add_handler(CommandHandler("add", add_anime))
    app.add_handler(CommandHandler("del", del_anime))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("bc", broadcast))
    app.add_handler(CommandHandler("bulkadd", bulk_add))
    app.add_handler(CommandHandler("fbc", forward_broadcast))
    app.add_handler(CommandHandler("uptime", uptime))
    app.add_handler(CommandHandler("groups", groups))
    app.add_handler(CommandHandler("stick", set_start_sticker_cmd))
    app.add_handler(CommandHandler("cancelreply", cancel_reply))
    app.add_handler(CommandHandler("addchannel", addchannel))
    app.add_handler(CommandHandler("delchannel", delchannel))
    app.add_handler(CommandHandler("channels", channels))


    # ==========================
    # OWNER-ONLY SUDO MANAGEMENT
    # ==========================
    app.add_handler(CommandHandler("addsudo", add_sudo))
    app.add_handler(CommandHandler("delsudo", del_sudo))
    app.add_handler(CommandHandler("sudolist", sudo_list))


    # ==========================
    # MESSAGE HANDLERS
    # ==========================
    # NOTE: Only admin_request_reply remains here.
    # direct_search has been REMOVED — anime search is command-only now.
    # Normal text messages must NEVER trigger anime search.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            admin_request_reply,
        ),
        group=0,
    )


    # ==========================
    # CALLBACK / INLINE
    # ==========================
    app.add_handler(
        CallbackQueryHandler(
            groups_callback,
            pattern="^groups_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(button_click)
    )

    app.add_handler(
        InlineQueryHandler(inline_query)
    )


    # ==========================
    # GROUP EVENTS
    # ==========================
    app.add_handler(
        ChatMemberHandler(
            chat_member_update,
            ChatMemberHandler.MY_CHAT_MEMBER,
        )
    )

    app.add_handler(
        ChatMemberHandler(
            channel_member_update,
            ChatMemberHandler.CHAT_MEMBER,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_members
        )
    )


    # ==============================
    # LOCAL / RENDER MODE
    # ==============================
    PORT = int(os.environ.get("PORT", 10000))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")


    # ==============================
    # RENDER WEBHOOK
    # ==============================
    if RENDER_URL:

        WEBHOOK_URL = f"{RENDER_URL}/{BOT_TOKEN}"

        print("🌐 Running in Render Webhook Mode")
        print(f"🌐 Webhook URL: {WEBHOOK_URL}")

        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True,
        )


    # ==============================
    # LOCAL POLLING
    # ==============================
    else:

        print("🤖 Running in Local Polling Mode")
        print("📡 Waiting for Telegram updates...")

        app.run_polling(
            drop_pending_updates=True
        )


# ==============================
# ENTRY POINT
# ==============================
if __name__ == "__main__":
    main()
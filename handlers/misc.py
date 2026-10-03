# ==============================
# MISC COMMANDS (EXACT ORIGINAL)
# ==============================

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
import random

from utils.filters import BOT_STATUS
from utils.sudo import is_owner_or_sudo


ROAST_LINES = [
    "😂 {mention}, tu filler episode jaisa hai — skip kar dete hain!",
    "🔥 {mention} ka IQ anime recap se bhi kam lag raha hai!",
    "😴 {mention}, tu itna boring hai ki OST bhi so gaya!",
    "🤡 {mention} lagta hai training arc miss kar gaya!",
    "💀 {mention}, villain bhi tujhe seriously nahi leta!",
    "🐌 {mention} ka reaction time Naruto ke childhood se slow hai!",
    "📉 {mention}, tera power level over 9000… negative me!",
    "🧠 {mention}, tera brain buffering pe hai kya?",
    "👀 {mention}, tu background character lag raha hai!",
    "⚰️ {mention}, tera comeback arc cancel ho chuka hai!",
    "🎭 {mention}, acting achhi hai par story weak hai!",
    "🫠 {mention}, tu filler ka filler lag raha hai!",
    "🚫 {mention}, tera screen time kam karna padega!",
    "🥲 {mention}, tera aura bhi low budget hai!",
    "😈 {mention}, tu villain bhi bane to side villain lage!",
    "📺 {mention}, tu ad-break jaisa hai — irritate karta hai!",
    "🌀 {mention}, tera jutsu loading me hi reh gaya!",
    "😬 {mention}, tera confidence sirf intro tak tha!",
    "🐸 {mention}, tu evolution skip karke aaya lagta hai!",
    "📉 {mention}, tera character development zero hai!",
    "🎮 {mention}, tu NPC vibes de raha hai!",
    "🥱 {mention}, tujhe dekh ke anime pause kar diya!",
    "🪦 {mention}, tera arc ek episode me khatam!",
    "⚠️ {mention}, tu spoiler jaisa hai — sab kharab!",
    "🫡 {mention}, tu try karta hai… bas wahi tak!",
    "💤 {mention}, tu sleep mode me hi theek hai!",
    "🎯 {mention}, tera aim filler jaisa hai!",
    "🧃 {mention}, tu low-energy protagonist hai!",
    "🗑️ {mention}, tera logic recycle bin me hai!",
    "📦 {mention}, tu side quest bhi complete nahi kar paya!",
    "🦥 {mention}, tu slow motion me paida hua tha kya?",
    "🫥 {mention}, tera presence invisible hai!",
    "📉 {mention}, tera hype sirf trailer tak tha!",
    "🎬 {mention}, director ne tujhe cut kar diya!",
    "🧊 {mention}, tera attitude bhi thanda aur bekaar hai!",
    "⚔️ {mention}, tu sword uthaye bina hi haar gaya!",
    "📚 {mention}, tu rules padh ke bhi follow nahi karta!",
    "🎧 {mention}, tera theme song bhi boring hai!",
    "🧩 {mention}, tu incomplete puzzle jaisa hai!",
    "🪙 {mention}, tu coin flip me bhi haar jata hai!",
    "📛 {mention}, tera naam yaad rakhna bhi mushkil hai!",
    "🥴 {mention}, tu lagta hai filler universe se aaya hai!",
    "🛑 {mention}, tera arc yahin end hota hai!",
    "📉 {mention}, tera graph sirf neeche jaata hai!",
    "🧟 {mention}, tu zombie jaisa lag raha hai!",
    "📢 {mention}, tu zyada bolta hai par kaam zero!",
    "🎯 {mention}, tera focus bhi missing hai!",
    "🫤 {mention}, tu hero nahi, confusion hai!",
    "📼 {mention}, tu old cassette jaisa atak gaya hai!"
]

async def roast_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("😅 Roast ka asli maza group me aata hai bhai!")

    user = None
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    elif context.args:
        try:
            user = await context.bot.get_chat(context.args[0])
        except: pass
        
    if not user:
        return await update.message.reply_text("⚠️ Kisko roast karna hai?\n👉 Reply karo ya username do 😁")
    if user.id == update.effective_user.id:
        return await update.message.reply_text("😂 Khud ko roast? Bhai self-damage mat kar!")
    if await is_owner_or_sudo(user.id):
        return await update.message.reply_text("👑 <b>Ye Mera Owner hai!</b>\n⚠️ Owner ko roast karna mana hai 😌", parse_mode="HTML")

    mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
    roast = random.choice(ROAST_LINES).format(mention=mention)
    await update.message.reply_text(roast, parse_mode="HTML")


# ==============================
# ID & OWNER & ADMINLIST
# ==============================

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return await update.message.reply_text(f"🆔 <b>Your ID:</b> <code>{update.effective_user.id}</code>", parse_mode="HTML")
    
    user = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    await update.message.reply_text(
        f"🆔 <b>ID Information</b>\n\n👤 <b>User:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a>\n🆔 <b>User ID:</b> <code>{user.id}</code>\n👥 <b>Group ID:</b> <code>{update.effective_chat.id}</code>", 
        parse_mode="HTML"
    )

async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private": return await update.message.reply_text("❌ Ye command sirf groups ke liye hai")
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        owner = next((admin.user for admin in admins if admin.status == ChatMemberStatus.OWNER), None)
        if not owner: return await update.message.reply_text("❌ Hokage nahi mila")
        
        await update.message.reply_text(f"👑 <b>Group Owner Detected!</b>\n\n👤 <a href='tg://user?id={owner.id}'>{owner.first_name}</a> <b>(Hokage)</b>\n🆔 <b>User ID:</b> <code>{owner.id}</code>", parse_mode="HTML")
    except:
        await update.message.reply_text("❌ Admin rights required")

async def adminlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text("❌ Group only command.")

    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)

        owner = None
        admin_list = []

        for admin in admins:
            if admin.user.is_bot:
                continue

            if admin.status == ChatMemberStatus.OWNER:
                owner = admin.user
            else:
                if admin.can_restrict_members:
                    title = "🔥 War Commander"
                elif admin.can_delete_messages:
                    title = "⚔️ Shadow Captain"
                elif admin.can_invite_users:
                    title = "🎯 Elite Recruiter"
                else:
                    title = "🎖️ Chunin"

                admin_list.append((admin.user, title))

        text = "👑 <b>Anime Admin Council</b>\n"
        text += "━━━━━━━━━━━━━━━━━━\n\n"

        if owner:
            text += f"👑 <a href='tg://user?id={owner.id}'>{owner.first_name}</a> — <i>Hokage</i>\n\n"

        for user, title in admin_list:
            text += f"• <a href='tg://user?id={user.id}'>{user.first_name}</a> — <i>{title}</i>\n"

        await update.message.reply_text(text, parse_mode="HTML")

    except:
        await update.message.reply_text("❌ Admin rights required.")
        

# ==============================
# SYSTEM CONTROLS & HELP
# ==============================

async def bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner_or_sudo(update.effective_user.id): return
    BOT_STATUS["active"] = False
    await update.message.reply_text("🛑 Bot turned OFF.")

async def bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_owner_or_sudo(update.effective_user.id): return
    BOT_STATUS["active"] = True
    await update.message.reply_text("✅ Bot turned ON.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot Alive ✅")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📜 <b>Bot Commands:</b>\n\n"
        "• /start - Start bot\n"
        "• /anime [name] - Exact Anime Search\n"
        "• /direct_on&off - To On/Off Direct Search In Gc\n"
        "• /search [name] - Partial Search\n"
        "• /btn [name] - Button Style Search\n"
        "• /animelist - Browse Anime List\n"
        "• /id - Get Profile/Group IDs\n"
        "• /owner - View Group Owner\n"
        "• /adminlist - View Admin Squad\n"
        "• /roast - Roast someone (reply or tag)\n"
        "• /daily - Get Daily Coins\n"
        "• /balance - Check Your Coins\n"
        "• /myref - Get Referral Link"
    )
    await update.message.reply_text(text, parse_mode="HTML")
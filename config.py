# ==============================
# CONFIG FILE (ENV + CONSTANTS)
# ==============================

from dotenv import load_dotenv
import os

load_dotenv()

# 🔐 ENV VARIABLES
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = os.getenv("OWNER_ID")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# ⚠️ SAFETY CHECK
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in .env")

if not MONGO_URI:
    raise ValueError("MONGO_URI is missing in .env")

if not OWNER_ID:
    raise ValueError("OWNER_ID is missing in .env")

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    raise ValueError("OWNER_ID must be a valid integer")

if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY is missing in .env")

# ==============================
# BOT SETTINGS
# ==============================

# ⚠️ LEGACY — kept for backward compatibility. No longer the primary
# force-sub source of truth. New force-sub logic uses
# OWNER_FORCE_CHANNEL_ID / OWNER_FORCE_CHANNEL_LINK below.
FORCE_CHANNEL = "@Anime_Stream_Zone"

# Numeric channel ID used for force-sub membership checks.
OWNER_FORCE_CHANNEL_ID = -1003543490433

# Public invite link of the main/owner channel.
OWNER_FORCE_CHANNEL_LINK = "https://t.me/+DVBuGuuBJUI5M2Rl"

REPORT_GROUP_ID = -1003964165574

ANIME_PER_PAGE = 15

# ==============================
# MEDIA
# ==============================

START_PHOTO = "https://files.catbox.moe/ichom4.jpg"
GROUP_PHOTO = "https://files.catbox.moe/ichom4.jpg"
# ==============================
# SYSTEM COMMAND IMAGES
# ==============================

PING_PHOTO = "https://files.catbox.moe/odasqu.jpg"
BSTATS_PHOTO = "https://files.catbox.moe/oqktfu.jpg"

WELCOME_EMOJIS = ["👋", "✨", "🌸", "🔥", "💫"]

# ==============================
# START ANIMATION CONFIG
# ==============================

START_ANIMATION_ENABLED = True

START_PRIVATE_ANIMATION = True
START_GROUP_ANIMATION = False

START_EMOJI_ENABLED = True

START_STICKER_ENABLED = True
DEFAULT_START_STICKER_ID = ""

START_TEXT_ANIMATION_ENABLED = True

START_ANIMATION_TEXTS = [
    "𝀚𝆭ꪳ͢Iηιτιαɭ̕ιᴢιηɢ...🦋𝅯͢𓂃",
    "ʟ𝅝᪲ͥ̌ʌ᪵ᴅᛧ꒖ɢ....!🌓🤍",
    "͢⎯꯭ໍ𝆺໋͢𝐀꯭ʟ꯭𐌼꯭៰꯭𝛅꯭𝛕꯭ꤪꤦꤨ ꝛ꯭̥𖾔꯭𝛂꯭ᴅ꯭ʏ꯭... 🌷꯭𝀚໋",
]

START_EMOJI_DELETE_DELAY = 1.0
START_STICKER_DELETE_DELAY = 1.0
START_TEXT_DELETE_DELAY = 1.0
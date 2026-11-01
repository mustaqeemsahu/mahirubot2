"""MahiruBot2 configuration.

Keep secrets in environment variables; never commit your .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Required credentials
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = os.getenv("OWNER_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in .env")
if not MONGO_URI:
    raise ValueError("MONGO_URI is missing in .env")
if not OWNER_ID:
    raise ValueError("OWNER_ID is missing in .env")

try:
    OWNER_ID = int(OWNER_ID)
except (TypeError, ValueError) as exc:
    raise ValueError("OWNER_ID must be a valid integer") from exc

# Optional external API. The bot must still start without TMDb configured.
TMDB_API_KEY = os.getenv("TMDB_API_KEY") or None

# Channel and group settings
FORCE_CHANNEL = "@Anime_Stream_Zone"  # Legacy compatibility
OWNER_FORCE_CHANNEL_ID = -1003543490433
OWNER_FORCE_CHANNEL_LINK = "https://t.me/+DVBuGuuBJUI5M2Rl"
REPORT_GROUP_ID = -1003964165574
MAIN_CHANNEL_URL = "https://t.me/Anime_Stream_Zone"
SUPPORT_GROUP_URL = "https://t.me/Anime_Search_Zone"

# Pagination
ANIME_PER_PAGE = 15

# Media
START_PHOTO = "https://files.catbox.moe/ichom4.jpg"
GROUP_PHOTO = "https://files.catbox.moe/ichom4.jpg"
PING_PHOTO = "https://files.catbox.moe/odasqu.jpg"
BSTATS_PHOTO = "https://files.catbox.moe/oqktfu.jpg"

# Retained because database/mongo.py and the existing /stick command use it.
DEFAULT_START_STICKER_ID = ""

# Existing group welcome configuration
WELCOME_EMOJIS = ["👋", "✨", "🌸", "🔥", "💫"]

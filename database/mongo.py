# ==============================
# MONGODB + CACHE + FAST SEARCH
# ==============================

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DeleteOne
from config import MONGO_URI, DEFAULT_START_STICKER_ID, OWNER_ID
import time

# ==============================
# CONNECTION
# ==============================

client = AsyncIOMotorClient(MONGO_URI)
db = client["AnimeBotDB"]

# Collections
users_col = db["users"]
groups_col = db["groups"]
anime_col = db["anime"]
warns_col = db["warns"]
sudo_users_col = db["sudo_users"]

# ==============================
# CACHE SYSTEM
# ==============================

ANIME_CACHE = []
CACHE_TIME = 0
CACHE_TTL = 300  # 5 minutes

# ==============================
# USERS SYSTEM
# ==============================

async def add_user(user_id: int):
    if not await users_col.find_one({"_id": user_id}):
        await users_col.insert_one({"_id": user_id})


async def get_all_users():
    return [u["_id"] async for u in users_col.find()]
async def total_users():
    return await users_col.count_documents({})

async def remove_user(user_id: int):
    await users_col.delete_one({"_id": user_id})


async def remove_group(chat_id: int):
    await groups_col.delete_one({"_id": chat_id})


# ==============================
# GROUP SYSTEM
# ==============================

async def add_group(chat_id: int):
    await groups_col.update_one(
        {"_id": chat_id},
        {"$set": {"_id": chat_id}},
        upsert=True
    )

async def remove_group(chat_id: int):
    await groups_col.delete_one({"_id": chat_id})

async def get_all_groups():
    """
    Return a list of raw integer chat IDs (not Mongo documents).

    Example:
        [-1001234567890, -1009876543210]
    """
    return [
        group["_id"]
        async for group in groups_col.find({}, {"_id": 1})
    ]


async def total_groups():
    return await groups_col.count_documents({})
# ==============================
# GROUP MEMBERS TRACKING
# ==============================

group_members_col = db["group_members"]


async def ensure_group_members_indexes():
    """
    Ensure indexes for the group_members collection.
    Idempotent — safe to call multiple times.
    """
    try:
        await group_members_col.create_index(
            [("group_id", 1), ("user_id", 1)],
            unique=True,
            name="group_user_unique",
        )
    except Exception as e:
        print(f"[MONGO] group_members index error: {e}")


async def track_group_member(
    group_id: int,
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_bot: bool = False,
):
    """
    Upsert a group member record.

    - Uses compound (group_id, user_id) uniqueness.
    - Updates last_seen and profile fields on every call.
    - Preserves first_seen once set.
    """
    from datetime import datetime

    try:
        group_id = int(group_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    now = datetime.utcnow()

    try:
        await group_members_col.update_one(
            {"group_id": group_id, "user_id": user_id},
            {
                "$set": {
                    "group_id": group_id,
                    "user_id": user_id,
                    "username": username or None,
                    "first_name": first_name or None,
                    "last_name": last_name or None,
                    "is_bot": bool(is_bot),
                    "last_seen": now,
                },
                "$setOnInsert": {
                    "first_seen": now,
                },
            },
            upsert=True,
        )
        return True
    except Exception as e:
        print(f"[MONGO] track_group_member failed: {e}")
        return False


async def get_group_members(group_id: int):
    """
    Return a list of member documents for a group.
    Includes only {user_id, username, first_name, last_name, is_bot}.
    """
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return []

    results = []
    try:
        async for doc in group_members_col.find(
            {"group_id": group_id},
            {
                "_id": 0,
                "user_id": 1,
                "username": 1,
                "first_name": 1,
                "last_name": 1,
                "is_bot": 1,
            },
        ):
            results.append(doc)
    except Exception as e:
        print(f"[MONGO] get_group_members failed: {e}")

    return results


async def remove_group_member(group_id: int, user_id: int):
    """Remove a single tracked member record. Returns True if deleted."""
    try:
        group_id = int(group_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    try:
        result = await group_members_col.delete_one(
            {"group_id": group_id, "user_id": user_id}
        )
        return result.deleted_count > 0
    except Exception as e:
        print(f"[MONGO] remove_group_member failed: {e}")
        return False


async def remove_group_members_for_group(group_id: int):
    """Remove all tracked members for a group. Returns deleted count."""
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return 0

    try:
        result = await group_members_col.delete_many({"group_id": group_id})
        return result.deleted_count
    except Exception as e:
        print(f"[MONGO] remove_group_members_for_group failed: {e}")
        return 0


# ==============================
# ANIME SYSTEM (CACHED)
# ==============================

async def load_anime_cache():
    global ANIME_CACHE, CACHE_TIME

    ANIME_CACHE = [a async for a in anime_col.find()]
    CACHE_TIME = time.time()


async def get_all_anime():
    global CACHE_TIME

    # Reload cache if expired
    if time.time() - CACHE_TIME > CACHE_TTL or not ANIME_CACHE:
        await load_anime_cache()

    return ANIME_CACHE


async def add_anime_db(
    name,
    keys,
    sticker,
    hindi_link=None,
    english_link=None
):
    data = {
        "name": name,
        "keys": keys,
        "sticker": sticker
    }

    # Save only if provided
    if hindi_link:
        data["hindi_link"] = hindi_link

    if english_link:
        data["english_link"] = english_link

    # Backward compatibility
    if not hindi_link and not english_link:
        data["link"] = ""

    await anime_col.update_one(
        {"name": name},
        {"$set": data},
        upsert=True
    )

    # Refresh cache
    await load_anime_cache()

async def delete_anime_db(name):

    result = await anime_col.delete_one(
        {
            "name": {
                "$regex": f"^{name}$",
                "$options": "i"
            }
        }
    )

    await load_anime_cache()

    return result.deleted_count

# ==============================
# FAST SEARCH (INDEX BASED)
# ==============================

async def create_indexes():
    await anime_col.create_index("name")
    await anime_col.create_index("keys")
    await ensure_group_members_indexes()


# ==============================
# SUDO SYSTEM
# ==============================

async def add_sudo_user(user_id: int, added_by: int):
    """
    Add a Sudo user.

    - Owner cannot be added as Sudo.
    - Uses numeric Telegram user ID as _id.
    - Returns True on success, False on invalid input/failure.
    """
    try:
        user_id = int(user_id)
        added_by = int(added_by)
    except (TypeError, ValueError):
        return False

    if user_id == OWNER_ID:
        return False

    await sudo_users_col.update_one(
        {"_id": user_id},
        {
            "$set": {
                "added_by": added_by,
            },
            "$setOnInsert": {
                "added_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    return True


async def remove_sudo_user(user_id: int):
    """
    Remove a Sudo user.

    - Owner cannot be removed via this path.
    - Returns True only if a document was deleted.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    if user_id == OWNER_ID:
        return False

    result = await sudo_users_col.delete_one({"_id": user_id})
    return result.deleted_count > 0


async def is_sudo_user(user_id: int) -> bool:
    """
    Return True if the given user is a Sudo user.

    - Owner is NOT returned as Sudo here.
    - Invalid IDs return False.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    if user_id == OWNER_ID:
        return False

    doc = await sudo_users_col.find_one({"_id": user_id}, {"_id": 1})
    return doc is not None


async def get_all_sudo_users():
    """
    Return a list of Sudo user IDs (ints), not full documents.
    """
    return [
        doc["_id"]
        async for doc in sudo_users_col.find({}, {"_id": 1})
    ]


async def total_sudo_users():
    return await sudo_users_col.count_documents({})


# ==========================================================
# REQUEST SYSTEM DATABASE
# ==========================================================

from datetime import datetime
import random

requests_col = db["requests"]


async def generate_request_id():
    """Generate unique request ID like REQ100123"""
    while True:
        req_id = f"REQ{random.randint(100000, 999999)}"
        exists = await requests_col.find_one({"_id": req_id})
        if not exists:
            return req_id


async def create_request(
    user_id: int,
    username: str,
    full_name: str,
    anime: str,
    language: str,
    dub: str,
    season: str,
    extra: str,
    tmdb_id=None,
    tmdb_title="",
    tmdb_original_title="",
    tmdb_overview="",
    tmdb_poster_url="",
    tmdb_backdrop_url="",
    tmdb_first_air_date="",
    tmdb_genres=None,
    tmdb_rating=None,
    tmdb_vote_count=None,
    tmdb_popularity=None,
):
    """
    Create a new anime request.

    TMDB metadata is OPTIONAL. If `tmdb_id` is provided, a nested
    `tmdb` object is stored alongside the request. Otherwise the
    request is stored exactly as before (no fake tmdb object).
    """
    req_id = await generate_request_id()

    if tmdb_genres is None:
        tmdb_genres = []

    data = {
        "_id": req_id,
        "user_id": user_id,
        "username": username or "",
        "full_name": full_name,
        "anime": anime,
        "language": language,
        "dub": dub,
        "season": season,
        "extra": extra,
        "status": "Pending",
        "admin_reply": "",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # Optional TMDB metadata block — only if a real TMDB id is present
    if tmdb_id:
        data["tmdb"] = {
            "id": tmdb_id,
            "title": tmdb_title or "",
            "original_title": tmdb_original_title or "",
            "overview": tmdb_overview or "",
            "poster_url": tmdb_poster_url or "",
            "backdrop_url": tmdb_backdrop_url or "",
            "first_air_date": tmdb_first_air_date or "",
            "genres": tmdb_genres or [],
            "rating": tmdb_rating,
            "vote_count": tmdb_vote_count,
            "popularity": tmdb_popularity,
        }

    await requests_col.insert_one(data)
    return req_id


async def get_request(req_id: str):
    return await requests_col.find_one({"_id": req_id})


async def update_request_status(
    req_id: str,
    status: str,
    admin_reply: str = "",
):
    await requests_col.update_one(
        {"_id": req_id},
        {
            "$set": {
                "status": status,
                "admin_reply": admin_reply,
                "updated_at": datetime.utcnow(),
            }
        },
    )


async def delete_request(req_id: str):
    await requests_col.delete_one({"_id": req_id})


async def get_pending_requests():
    requests = []
    async for req in requests_col.find({"status": "Pending"}):
        requests.append(req)
    return requests


async def get_user_requests(user_id: int):
    requests = []
    async for req in requests_col.find({"user_id": user_id}):
        requests.append(req)
    return requests


async def total_requests():
    return await requests_col.count_documents({})


async def pending_requests():
    return await requests_col.count_documents(
        {"status": "Pending"}
    )


async def request_exists(user_id: int, anime: str, language: str):
    """
    Prevent duplicate pending requests.
    """
    return await requests_col.find_one(
        {
            "user_id": user_id,
            "anime": {"$regex": f"^{anime}$", "$options": "i"},
            "language": language,
            "status": "Pending",
        }
            )


async def update_request_reply(req_id, reply):

    await requests_col.update_one(
        {"_id": req_id},
        {
            "$set": {
                "admin_reply": reply
            }
        }
    )


# ==============================
# WARN SYSTEM
# ==============================

WARN_LIMIT = 3

async def add_warn_db(chat_id, user_id, reason):
    data = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})

    if not data:
        await warns_col.insert_one({
            "chat_id": chat_id,
            "user_id": user_id,
            "count": 1,
            "reasons": [reason]
        })
        return 1

    new_count = data["count"] + 1
    reasons = data["reasons"] + [reason]

    await warns_col.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"count": new_count, "reasons": reasons}}
    )

    return new_count


async def get_warns_db(chat_id, user_id):
    data = await warns_col.find_one({"chat_id": chat_id, "user_id": user_id})
    return data if data else {"count": 0, "reasons": []}


async def reset_warns_db(chat_id, user_id):
    await warns_col.delete_one({"chat_id": chat_id, "user_id": user_id})


# ==============================
# START SETTINGS
# ==============================

start_settings_col = db["start_settings"]


async def get_start_sticker():
    """
    Return the active start sticker ID.

    Priority:
        1. Custom sticker stored in MongoDB (start_settings._id = "main")
        2. Fallback to DEFAULT_START_STICKER_ID from config

    Never raises on DB error — always falls back to the default.
    """
    try:
        doc = await start_settings_col.find_one({"_id": "main"})

        if doc:
            sticker_id = doc.get("sticker_id")
            if sticker_id:
                return sticker_id

    except Exception:
        pass

    return DEFAULT_START_STICKER_ID


async def set_start_sticker(sticker_id: str):
    """
    Save a custom start sticker to MongoDB.

    - Strips surrounding whitespace
    - Rejects empty values
    - Uses upsert on the single "_id": "main" document
    - Returns the stored sticker_id on success, or None on failure
    """
    if not sticker_id:
        return None

    sticker_id = sticker_id.strip()

    if not sticker_id:
        return None

    await start_settings_col.update_one(
        {"_id": "main"},
        {"$set": {"sticker_id": sticker_id}},
        upsert=True
    )

    return sticker_id


async def clear_start_sticker():
    """
    Remove the custom start sticker.

    After clearing, get_start_sticker() will fall back to
    DEFAULT_START_STICKER_ID automatically.
    """
    await start_settings_col.update_one(
        {"_id": "main"},
        {"$unset": {"sticker_id": ""}},
        upsert=True
    )

# ==============================
# PROMOTIONAL CHANNELS (FORCE-SUB)
# ==============================

promotional_channels_col = db["promotional_channels"]


async def add_promotional_channel(name: str, channel_id: int, channel_link: str):
    """
    Add or re-enable a promotional channel.

    Prevents duplicate channel IDs by re-using an existing document
    for the same channel_id if present.
    """
    from datetime import datetime

    name = (name or "").strip()
    channel_link = (channel_link or "").strip()

    if not name or not channel_link:
        return False

    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return False

    # Duplicate prevention: upsert on channel_id
    await promotional_channels_col.update_one(
        {"channel_id": channel_id},
        {
            "$set": {
                "name": name,
                "channel_link": channel_link,
                "enabled": True,
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow(),
            },
        },
        upsert=True,
    )

    return True

async def get_promotional_channels(active_only: bool = True):
    """
    Return a list of promotional channel documents.
    If active_only=True, only returns documents with enabled == True.
    """
    query = {"enabled": True} if active_only else {}

    results = []
    async for doc in promotional_channels_col.find(query):
        results.append(doc)
    return results


async def remove_promotional_channel(channel_id: int):
    """
    Remove a promotional channel by its numeric channel ID.
    Returns True if a document was deleted.
    """
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return False

    result = await promotional_channels_col.delete_one({"channel_id": channel_id})
    return result.deleted_count > 0


async def channel_exists(channel_id: int) -> bool:
    """Return True if the given channel ID is already registered."""
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return False

    doc = await promotional_channels_col.find_one({"channel_id": channel_id})
    return doc is not None
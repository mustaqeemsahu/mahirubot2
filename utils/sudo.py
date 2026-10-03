# ==============================
# PERMISSION / SUDO LAYER
# ==============================
#
# Central permission helper for MahiruShina-main.
#
# Roles:
#   OWNER       → config.OWNER_ID (permanent, not in MongoDB)
#   SUDO        → dynamic, stored in MongoDB via database.mongo
#   NORMAL USER → everyone else
#
# Command permission table:
#
#   OWNER
#   ├── All normal user commands
#   ├── All Sudo management commands
#   └── All Sudo-allowed bot management commands
#
#   SUDO
#   ├── All normal user commands
#   └── Explicitly allowed bot management commands
#
#   NORMAL USER
#   └── Normal user commands only
#
# Owner-only commands:
#   /addsudo
#   /delsudo
#   /sudolist
#
# Owner + Sudo commands:
#   /add
#   /del
#   /stats
#   /broadcast
#   /bc
#   /bulkadd
#   /fbc
#   /uptime
#   /groups
#   /stick
#   /cancelreply
#   /addchannel
#   /delchannel
#   /channels
# ==============================

from config import OWNER_ID
from database.mongo import is_sudo_user


# ==============================
# COMMAND PERMISSION SETS
# ==============================

SUDO_ALLOWED_COMMANDS = {
    "add",
    "del",
    "stats",
    "broadcast",
    "bc",
    "bulkadd",
    "fbc",
    "uptime",
    "groups",
    "stick",
    "cancelreply",
    "addchannel",
    "delchannel",
    "channels",
}

OWNER_ONLY_COMMANDS = {
    "addsudo",
    "delsudo",
    "sudolist",
}


# ==============================
# INTERNAL HELPERS
# ==============================

def _to_int(user_id):
    """Best-effort conversion to int. Returns None on failure."""
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _normalize_command(command: str) -> str:
    """Lowercase and strip leading slashes/spaces from a command name."""
    if not isinstance(command, str):
        return ""
    return command.strip().lower().lstrip("/")


# ==============================
# ROLE CHECKS
# ==============================

def is_owner(user_id: int) -> bool:
    """
    Return True if user_id matches the configured OWNER_ID.

    Safe against None / invalid input.
    Owner identification comes ONLY from config.OWNER_ID.
    """
    uid = _to_int(user_id)
    if uid is None:
        return False

    return uid == OWNER_ID


async def is_sudo(user_id: int) -> bool:
    """
    Return True if user_id is a Sudo user in MongoDB.

    - Owner is NOT returned as Sudo here.
    - Invalid IDs return False.
    - MongoDB failure returns False (fail-safe).
    """
    uid = _to_int(user_id)
    if uid is None:
        return False

    # Owner never depends on MongoDB
    if uid == OWNER_ID:
        return False

    try:
        return await is_sudo_user(uid)
    except Exception:
        return False


async def is_owner_or_sudo(user_id: int) -> bool:
    """
    Return True if user is Owner OR Sudo.

    Owner is checked first so it never depends on MongoDB.
    """
    if is_owner(user_id):
        return True

    return await is_sudo(user_id)


async def get_user_role(user_id: int) -> str:
    """
    Return the role string for a user:

        "owner"
        "sudo"
        "user"
    """
    if is_owner(user_id):
        return "owner"

    if await is_sudo(user_id):
        return "sudo"

    return "user"


# ==============================
# COMMAND PERMISSION CHECKS
# ==============================

async def can_use_sudo_command(user_id: int, command: str) -> bool:
    """
    Return True if the user may execute the given management command.

        Owner  → True for every management command
        Sudo   → True only if command is in SUDO_ALLOWED_COMMANDS
        User   → False
    """
    cmd = _normalize_command(command)

    if not cmd:
        return False

    # Owner has full access to all sudo-allowed commands.
    if is_owner(user_id):
        return True

    if not await is_sudo(user_id):
        return False

    return cmd in SUDO_ALLOWED_COMMANDS


def can_use_owner_command(user_id: int, command: str) -> bool:
    """
    Return True if the user may execute the given Owner-only command.

        Owner  → True only if command is in OWNER_ONLY_COMMANDS
        Others → False
    """
    cmd = _normalize_command(command)

    if not cmd:
        return False

    if not is_owner(user_id):
        return False

    return cmd in OWNER_ONLY_COMMANDS


# ==============================
# TELEGRAM HANDLER CHECKS
# ==============================

PERMISSION_DENIED = "❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ."


async def require_owner(update, context) -> bool:
    """
    Handler-level check for Owner-only actions.

        Owner       → True
        Anyone else → send permission message, return False

    Never raises; fails safely if update.effective_user is missing.
    """
    user = getattr(update, "effective_user", None)

    if user is None:
        return False

    if is_owner(user.id):
        return True

    try:
        # Prefer replying to the incoming message / callback
        if getattr(update, "effective_message", None):
            await update.effective_message.reply_text(PERMISSION_DENIED)
        elif getattr(update, "callback_query", None):
            await update.callback_query.answer(
                PERMISSION_DENIED,
                show_alert=True,
            )
    except Exception:
        pass

    return False


async def require_sudo(update, context) -> bool:
    """
    Handler-level check for Sudo-or-Owner actions.

        Owner       → True
        Sudo        → True
        Normal user → send permission message, return False

    Never raises; fails safely if update.effective_user is missing.
    """
    user = getattr(update, "effective_user", None)

    if user is None:
        return False

    if await is_owner_or_sudo(user.id):
        return True

    try:
        if getattr(update, "effective_message", None):
            await update.effective_message.reply_text(PERMISSION_DENIED)
        elif getattr(update, "callback_query", None):
            await update.callback_query.answer(
                PERMISSION_DENIED,
                show_alert=True,
            )
    except Exception:
        pass

    return False
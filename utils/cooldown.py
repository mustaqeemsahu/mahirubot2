# ==============================
# COOLDOWN SYSTEM
# ==============================

import time

user_cooldown = {}

DEFAULT_COOLDOWN = 5


def check_cooldown(user_id, seconds=None):
    """
    Return True if the user may act, False if they're on cooldown.

    - `seconds` defaults to DEFAULT_COOLDOWN (5) if not provided.
    - On success, records the current timestamp.
    - Safe against invalid `seconds` values.
    """
    now = time.time()

    if seconds is None:
        seconds = DEFAULT_COOLDOWN

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = DEFAULT_COOLDOWN

    if user_id in user_cooldown:
        if now - user_cooldown[user_id] < seconds:
            return False

    user_cooldown[user_id] = now
    return True


def remaining_cooldown(user_id, seconds=None):
    """
    Return the remaining cooldown time in seconds for this user.
    Returns 0.0 if the user is not on cooldown.
    """
    now = time.time()

    if seconds is None:
        seconds = DEFAULT_COOLDOWN

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = DEFAULT_COOLDOWN

    if user_id not in user_cooldown:
        return 0.0

    remaining = seconds - (now - user_cooldown[user_id])
    return max(0.0, remaining)


def reset_cooldown(user_id):
    """Manually clear a user's cooldown."""
    user_cooldown.pop(user_id, None)
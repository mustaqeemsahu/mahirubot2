# ==============================
# JIKAN API CLIENT
# ==============================
# MyAnimeList data via https://api.jikan.moe/v4
#
# Features:
#   - Async httpx client
#   - Global rate limiter (2.5 req/sec ceiling)
#   - In-memory cache (5 min per query)
#   - Retry on 5xx / timeout (1 retry, 2s delay)
#   - Safe normalization of responses
#   - Never crashes the bot
#
# Rate limits enforced:
#   - Global: 400ms minimum between requests
#   - Per-query in-memory cache: 300s TTL
#   - No bulk population (respects Jikan guidelines)
# ==============================

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


# ==============================
# CONFIG
# ==============================

JIKAN_BASE = "https://api.jikan.moe/v4"
JIKAN_TIMEOUT = 10.0
JIKAN_MIN_INTERVAL = 0.4      # 400ms between requests globally
JIKAN_CACHE_TTL = 300         # 5 minutes in-memory
JIKAN_MAX_RETRIES = 1         # one retry on 5xx / timeout
JIKAN_RETRY_DELAY = 2.0       # seconds between retries


# ==============================
# GLOBAL STATE
# ==============================

_jikan_lock = asyncio.Lock()
_last_call_time = 0.0
_cache: dict = {}  # { cache_key: (expires_at, data) }

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Lazy-init a shared httpx client."""
    global _client

    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=JIKAN_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    return _client


async def close_jikan_client():
    """Call on bot shutdown to close the httpx client."""
    global _client

    if _client is not None and not _client.is_closed:
        try:
            await _client.aclose()
        except Exception as e:
            logger.warning("Failed to close Jikan client: %s", e)

    _client = None


# ==============================
# GLOBAL RATE LIMITER + RETRY
# ==============================

async def _rate_limited_get(path: str, params: dict | None = None, retries: int = JIKAN_MAX_RETRIES):
    """
    Perform a rate-limited GET against Jikan.

    - Global 400ms interval ensures we never exceed ~2.5 req/sec
      across all concurrent callers, well under Jikan's limits.
    - Retries once (configurable) on 5xx or timeout with a 2s delay.
    - Returns parsed JSON dict or None on failure.
    """
    global _last_call_time

    for attempt in range(retries + 1):

        # Wait our turn under the global lock
        async with _jikan_lock:
            now = time.monotonic()
            wait = JIKAN_MIN_INTERVAL - (now - _last_call_time)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call_time = time.monotonic()

        url = f"{JIKAN_BASE}{path}"

        try:
            client = await _get_client()
            response = await client.get(url, params=params or {})

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception as e:
                    logger.warning("Jikan invalid JSON: %s", e)
                    return None

            if response.status_code == 429:
                logger.warning("Jikan rate-limited (429)")
                return None

            if response.status_code == 404:
                logger.info("Jikan 404 for %s", path)
                return None

            # 5xx → retry
            if 500 <= response.status_code < 600:
                if attempt < retries:
                    logger.info(
                        "Jikan %s on %s — retrying in %.1fs",
                        response.status_code, path, JIKAN_RETRY_DELAY,
                    )
                    await asyncio.sleep(JIKAN_RETRY_DELAY)
                    continue
                logger.warning("Jikan server error %s (gave up)", response.status_code)
                return None

            logger.warning("Jikan unexpected status %s", response.status_code)
            return None

        except asyncio.TimeoutError:
            if attempt < retries:
                logger.info("Jikan timeout on %s — retrying in %.1fs", path, JIKAN_RETRY_DELAY)
                await asyncio.sleep(JIKAN_RETRY_DELAY)
                continue
            logger.warning("Jikan timeout (gave up)")
            return None

        except httpx.HTTPError as e:
            if attempt < retries:
                logger.info("Jikan HTTP error — retrying in %.1fs", JIKAN_RETRY_DELAY)
                await asyncio.sleep(JIKAN_RETRY_DELAY)
                continue
            logger.warning("Jikan HTTP error (gave up): %s", e)
            return None

        except Exception as e:
            logger.warning("Jikan unexpected error: %s", e)
            return None

    return None


# ==============================
# CACHE
# ==============================

def _cache_get(key: str):
    entry = _cache.get(key)
    if not entry:
        return None

    expires_at, data = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None

    return data


def _cache_set(key: str, data):
    _cache[key] = (time.time() + JIKAN_CACHE_TTL, data)


# ==============================
# NORMALIZATION
# ==============================

def _safe_str(v, default=""):
    if v is None:
        return default
    return str(v)


def _safe_int(v, default=0):
    try:
        if v is None:
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _normalize_anime(item: dict) -> dict:
    """Normalize a Jikan anime object into the project's schema."""
    if not isinstance(item, dict):
        return {}

    images = item.get("images") or {}
    jpg = images.get("jpg") or {}
    webp = images.get("webp") or {}

    # Prefer higher-res webp large, then jpg large, then defaults
    image_url = (
        webp.get("large_image_url")
        or jpg.get("large_image_url")
        or webp.get("image_url")
        or jpg.get("image_url")
    )

    genres = []
    for g in item.get("genres") or []:
        if isinstance(g, dict):
            name = g.get("name")
            if name:
                genres.append(str(name))

    studios = []
    for s in item.get("studios") or []:
        if isinstance(s, dict):
            name = s.get("name")
            if name:
                studios.append(str(name))

    aired = item.get("aired") or {}
    aired_from = aired.get("from")  # ISO date string or None

    return {
        "mal_id": _safe_int(item.get("mal_id")),
        "title": _safe_str(item.get("title") or item.get("title_english") or ""),
        "title_english": _safe_str(item.get("title_english")),
        "title_japanese": _safe_str(item.get("title_japanese")),
        "synopsis": _safe_str(item.get("synopsis")),
        "image_url": image_url,
        "type": _safe_str(item.get("type")),
        "episodes": _safe_int(item.get("episodes")),
        "status": _safe_str(item.get("status")),
        "aired_from": _safe_str(aired_from),
        "score": _safe_float(item.get("score")),
        "scored_by": _safe_int(item.get("scored_by")),
        "rank": _safe_int(item.get("rank")),
        "popularity": _safe_int(item.get("popularity")),
        "members": _safe_int(item.get("members")),
        "favorites": _safe_int(item.get("favorites")),
        "genres": genres,
        "studios": studios,
        "url": _safe_str(item.get("url")),
    }


# ==============================
# PUBLIC API
# ==============================

async def search_anime(query: str, limit: int = 5) -> list:
    """
    Search anime by name.

    Returns a list of normalized anime dicts. Empty list on failure.
    """
    if not query or not isinstance(query, str):
        return []

    query = query.strip()
    if not query:
        return []

    cache_key = f"search:{query.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _rate_limited_get(
        "/anime",
        params={
            "q": query,
            "limit": max(1, min(limit, 10)),
            "sfw": "true",
        },
    )

    if not data or not isinstance(data, dict):
        return []

    raw = data.get("data") or []
    if not isinstance(raw, list):
        return []

    results = [_normalize_anime(item) for item in raw]
    results = [r for r in results if r.get("mal_id")]

    _cache_set(cache_key, results)
    return results


async def get_anime_by_id(mal_id: int) -> dict | None:
    """
    Fetch full details for one anime by MAL ID.

    Returns normalized dict, or None.
    """
    try:
        mal_id = int(mal_id)
    except (TypeError, ValueError):
        return None

    if mal_id <= 0:
        return None

    cache_key = f"id:{mal_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _rate_limited_get(f"/anime/{mal_id}/full")

    if not data or not isinstance(data, dict):
        return None

    item = data.get("data")
    if not isinstance(item, dict):
        return None

    result = _normalize_anime(item)
    if not result.get("mal_id"):
        return None

    _cache_set(cache_key, result)
    return result


async def find_best_match(query: str) -> dict | None:
    """
    Convenience: search + pick top result, then fetch full details.

    Returns the detailed normalized dict, or None.

    NOTE: Jikan's first result is not guaranteed to be the correct
    anime — treat as best-effort.
    """
    results = await search_anime(query, limit=5)
    if not results:
        return None

    top = results[0]
    mal_id = top.get("mal_id")
    if not mal_id:
        return top

    details = await get_anime_by_id(mal_id)
    return details or top
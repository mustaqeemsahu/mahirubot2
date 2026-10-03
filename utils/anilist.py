# ==============================
# ANILIST API CLIENT
# ==============================
# Anime data via https://graphql.anilist.co
#
# Features:
#   - Async httpx client (GraphQL POST)
#   - Global rate limiter (30 req/min safe ceiling)
#   - In-memory cache (5 min per query)
#   - Retry on 5xx / timeout (1 retry, 2s delay)
#   - Safe normalization to the project's schema
#   - Never crashes the bot
#
# Rate limits:
#   - Global: 2s minimum between requests (30/min)
#   - Per-query in-memory cache: 300s TTL
# ==============================

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)


# ==============================
# CONFIG
# ==============================

ANILIST_URL = "https://graphql.anilist.co"
ANILIST_TIMEOUT = 12.0
ANILIST_MIN_INTERVAL = 2.0     # 2s between requests globally = 30/min
ANILIST_CACHE_TTL = 300        # 5 minutes in-memory
ANILIST_MAX_RETRIES = 1        # one retry on 5xx / timeout
ANILIST_RETRY_DELAY = 3.0      # seconds between retries


# ==============================
# GRAPHQL QUERIES
# ==============================

SEARCH_QUERY = """
query ($search: String, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title {
        romaji
        english
        native
      }
      description(asHtml: false)
      coverImage {
        extraLarge
        large
        medium
      }
      bannerImage
      format
      episodes
      duration
      status
      season
      seasonYear
      startDate {
        year
        month
        day
      }
      endDate {
        year
        month
        day
      }
      genres
      averageScore
      meanScore
      popularity
      favourites
      studios(isMain: true) {
        nodes {
          name
        }
      }
      siteUrl
    }
  }
}
"""

DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    description(asHtml: false)
    coverImage {
      extraLarge
      large
      medium
    }
    bannerImage
    format
    episodes
    duration
    status
    season
    seasonYear
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    genres
    averageScore
    meanScore
    popularity
    favourites
    studios(isMain: true) {
      nodes {
        name
      }
    }
    siteUrl
  }
}
"""


# ==============================
# GLOBAL STATE
# ==============================

_anilist_lock = asyncio.Lock()
_last_call_time = 0.0
_cache: dict = {}  # { cache_key: (expires_at, data) }

_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Lazy-init a shared httpx client."""
    global _client

    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=ANILIST_TIMEOUT,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    return _client


async def close_anilist_client():
    """Call on bot shutdown to close the httpx client."""
    global _client

    if _client is not None and not _client.is_closed:
        try:
            await _client.aclose()
        except Exception as e:
            logger.warning("Failed to close AniList client: %s", e)

    _client = None


# ==============================
# GLOBAL RATE LIMITER + RETRY
# ==============================

async def _rate_limited_post(query: str, variables: dict, retries: int = ANILIST_MAX_RETRIES):
    """
    Perform a rate-limited GraphQL POST to AniList.

    - Global 2s interval ensures we stay under 30 req/min.
    - Retries once on 5xx or timeout.
    - Returns parsed `data` dict, or None.
    """
    global _last_call_time

    payload = {"query": query, "variables": variables}

    for attempt in range(retries + 1):

        # Wait our turn under the global lock
        async with _anilist_lock:
            now = time.monotonic()
            wait = ANILIST_MIN_INTERVAL - (now - _last_call_time)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_call_time = time.monotonic()

        try:
            client = await _get_client()
            response = await client.post(ANILIST_URL, json=payload)

            if response.status_code == 200:
                try:
                    body = response.json()
                except Exception as e:
                    logger.warning("AniList invalid JSON: %s", e)
                    return None

                # GraphQL errors payload
                if body.get("errors"):
                    logger.warning("AniList GraphQL errors: %s", body.get("errors"))
                    return None

                return body.get("data")

            if response.status_code == 429:
                logger.warning("AniList rate-limited (429)")
                return None

            if response.status_code == 404:
                logger.info("AniList 404")
                return None

            if 500 <= response.status_code < 600:
                if attempt < retries:
                    logger.info(
                        "AniList %s — retrying in %.1fs",
                        response.status_code, ANILIST_RETRY_DELAY,
                    )
                    await asyncio.sleep(ANILIST_RETRY_DELAY)
                    continue
                logger.warning("AniList server error %s (gave up)", response.status_code)
                return None

            logger.warning("AniList unexpected status %s", response.status_code)
            return None

        except asyncio.TimeoutError:
            if attempt < retries:
                logger.info("AniList timeout — retrying in %.1fs", ANILIST_RETRY_DELAY)
                await asyncio.sleep(ANILIST_RETRY_DELAY)
                continue
            logger.warning("AniList timeout (gave up)")
            return None

        except httpx.HTTPError as e:
            if attempt < retries:
                logger.info("AniList HTTP error — retrying in %.1fs", ANILIST_RETRY_DELAY)
                await asyncio.sleep(ANILIST_RETRY_DELAY)
                continue
            logger.warning("AniList HTTP error (gave up): %s", e)
            return None

        except Exception as e:
            logger.warning("AniList unexpected error: %s", e)
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
    _cache[key] = (time.time() + ANILIST_CACHE_TTL, data)


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


def _format_date(date_obj: dict) -> str:
    """Format {year, month, day} into YYYY-MM-DD or partial."""
    if not isinstance(date_obj, dict):
        return ""

    y = date_obj.get("year")
    m = date_obj.get("month")
    d = date_obj.get("day")

    if not y:
        return ""

    parts = [f"{y:04d}"]
    if m:
        parts.append(f"{m:02d}")
        if d:
            parts.append(f"{d:02d}")

    return "-".join(parts)


def _normalize_anime(item: dict) -> dict:
    """Normalize an AniList Media object into the project's schema."""
    if not isinstance(item, dict):
        return {}

    title_obj = item.get("title") or {}
    title_romaji = _safe_str(title_obj.get("romaji"))
    title_english = _safe_str(title_obj.get("english"))
    title_native = _safe_str(title_obj.get("native"))

    # Prefer English, fallback to romaji, then native
    display_title = title_english or title_romaji or title_native

    cover = item.get("coverImage") or {}
    image_url = (
        cover.get("extraLarge")
        or cover.get("large")
        or cover.get("medium")
    )

    genres = []
    for g in item.get("genres") or []:
        if isinstance(g, str):
            genres.append(g)

    studios = []
    studios_obj = item.get("studios") or {}
    for s in studios_obj.get("nodes") or []:
        if isinstance(s, dict):
            name = s.get("name")
            if name:
                studios.append(str(name))

    start_date = _format_date(item.get("startDate"))
    end_date = _format_date(item.get("endDate"))

    # Build a human-readable status
    status = _safe_str(item.get("status"))
    season = _safe_str(item.get("season"))
    season_year = item.get("seasonYear")

    return {
        "anilist_id": _safe_int(item.get("id")),
        "title": display_title,
        "title_english": title_english,
        "title_romaji": title_romaji,
        "title_native": title_native,
        "synopsis": _safe_str(item.get("description")),
        "image_url": image_url,
        "banner_url": _safe_str(item.get("bannerImage")),
        "type": _safe_str(item.get("format")),
        "episodes": _safe_int(item.get("episodes")),
        "duration": _safe_int(item.get("duration")),
        "status": status,
        "season": season,
        "season_year": _safe_int(season_year),
        "aired_from": start_date,
        "aired_to": end_date,
        "score": _safe_float(item.get("averageScore")),
        "mean_score": _safe_float(item.get("meanScore")),
        "popularity": _safe_int(item.get("popularity")),
        "favourites": _safe_int(item.get("favourites")),
        "genres": genres,
        "studios": studios,
        "url": _safe_str(item.get("siteUrl")),
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

    limit = max(1, min(limit, 10))

    cache_key = f"search:{query.lower()}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _rate_limited_post(
        SEARCH_QUERY,
        {"search": query, "perPage": limit},
    )

    if not data or not isinstance(data, dict):
        return []

    page = data.get("Page") or {}
    raw = page.get("media") or []
    if not isinstance(raw, list):
        return []

    results = [_normalize_anime(item) for item in raw]
    results = [r for r in results if r.get("anilist_id")]

    _cache_set(cache_key, results)
    return results


async def get_anime_by_id(anilist_id: int) -> dict | None:
    """
    Fetch full details for one anime by AniList ID.

    Returns normalized dict, or None.
    """
    try:
        anilist_id = int(anilist_id)
    except (TypeError, ValueError):
        return None

    if anilist_id <= 0:
        return None

    cache_key = f"id:{anilist_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = await _rate_limited_post(DETAIL_QUERY, {"id": anilist_id})

    if not data or not isinstance(data, dict):
        return None

    item = data.get("Media")
    if not isinstance(item, dict):
        return None

    result = _normalize_anime(item)
    if not result.get("anilist_id"):
        return None

    _cache_set(cache_key, result)
    return result


async def find_best_match(query: str) -> dict | None:
    """
    Convenience: search + pick top result.

    Returns the top normalized dict, or None.
    """
    results = await search_anime(query, limit=5)
    if not results:
        return None

    return results[0]
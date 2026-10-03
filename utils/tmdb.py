# ==============================
# TMDB API SERVICE LAYER
# ==============================
#
# Pure async data service for The Movie Database (TMDB).
#
# Responsibilities:
#   - Talk to TMDB over HTTPS
#   - Normalize raw responses into consistent dicts
#   - Never crash the bot on TMDB failures
#
# Not responsible for:
#   - Telegram UI
#   - MongoDB
#   - Anime/non-anime classification
#   - /request, /anime, /search integration
# ==============================

import asyncio
import logging

import aiohttp

from config import TMDB_API_KEY


# ==============================
# LOGGING
# ==============================

logger = logging.getLogger(__name__)


# ==============================
# CONSTANTS
# ==============================

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

TMDB_TIMEOUT = aiohttp.ClientTimeout(total=10)


# ==============================
# SESSION MANAGEMENT
# ==============================

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    """
    Return a shared aiohttp session, creating it lazily.
    Session is reused across requests to avoid overhead.
    """
    global _session

    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=TMDB_TIMEOUT)

    return _session


async def close_tmdb_session() -> None:
    """
    Close the shared aiohttp session.
    Safe to call multiple times.
    """
    global _session

    if _session is not None and not _session.closed:
        try:
            await _session.close()
        except Exception as e:
            logger.warning("Failed to close TMDB session: %s", e)

    _session = None


# ==============================
# IMAGE URL HELPERS
# ==============================

def get_image_url(path: str | None, size: str = "original") -> str | None:
    """
    Build a full TMDB image URL from a relative path.

    - If path is None/empty → returns None.
    - If path is already a full URL → returns it unchanged.
    """
    if not path or not isinstance(path, str):
        return None

    path = path.strip()

    if not path:
        return None

    if path.startswith("http://") or path.startswith("https://"):
        return path

    # Ensure single slash between base and path
    if not path.startswith("/"):
        path = "/" + path

    return f"{TMDB_IMAGE_BASE_URL}/{size}{path}"


def get_poster_url(poster_path: str | None, size: str = "w500") -> str | None:
    """Build a poster URL. Default size: w500."""
    return get_image_url(poster_path, size)


def get_backdrop_url(backdrop_path: str | None, size: str = "w1280") -> str | None:
    """Build a backdrop URL. Default size: w1280."""
    return get_image_url(backdrop_path, size)


# ==============================
# INTERNAL REQUEST HELPER
# ==============================

async def _tmdb_get(
    endpoint: str,
    params: dict | None = None,
) -> dict | None:
    """
    Perform an async GET to TMDB.

    Returns the parsed JSON dict on success, or None on any failure.
    Never raises to callers.
    """
    if not TMDB_API_KEY:
        logger.warning("TMDB_API_KEY is not configured — skipping TMDB request")
        return None

    if not endpoint:
        return None

    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    url = f"{TMDB_BASE_URL}{endpoint}"

    request_params = dict(params or {})
    request_params["api_key"] = TMDB_API_KEY

    try:
        session = await _get_session()

        async with session.get(url, params=request_params) as response:

            status = response.status

            if status == 200:
                try:
                    return await response.json()
                except Exception as e:
                    logger.warning("TMDB returned invalid JSON: %s", e)
                    return None

            if status == 401:
                logger.error("TMDB request failed: HTTP 401 (invalid API key)")
                return None

            if status == 404:
                logger.warning("TMDB request failed: HTTP 404 (not found)")
                return None

            if status == 429:
                logger.warning("TMDB request failed: HTTP 429 (rate limited)")
                return None

            if 500 <= status < 600:
                logger.warning("TMDB request failed: HTTP %s (server error)", status)
                return None

            logger.warning("TMDB request failed: HTTP %s", status)
            return None

    except asyncio.TimeoutError:
        logger.warning("TMDB request timeout")
        return None

    except aiohttp.ClientError as e:
        logger.warning("TMDB client error: %s", e)
        return None

    except Exception as e:
        logger.warning("TMDB unexpected error: %s", e)
        return None


# ==============================
# NORMALIZATION HELPERS
# ==============================

def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_search_item(item: dict) -> dict:
    """
    Normalize a single /search/tv result into the project's schema.
    """
    title = _safe_str(item.get("name") or item.get("original_name"))
    original_title = _safe_str(item.get("original_name")) or title

    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path")

    return {
        "tmdb_id": _safe_int(item.get("id")),
        "title": title,
        "original_title": original_title,
        "overview": _safe_str(item.get("overview")),
        "poster_path": poster_path or None,
        "poster_url": get_poster_url(poster_path),
        "backdrop_path": backdrop_path or None,
        "backdrop_url": get_backdrop_url(backdrop_path),
        "first_air_date": item.get("first_air_date") or None,
        "rating": _safe_float(item.get("vote_average")),
        "vote_count": _safe_int(item.get("vote_count")),
        "popularity": _safe_float(item.get("popularity")),
    }


def _normalize_details(data: dict) -> dict:
    """
    Normalize a single /tv/{id} response into the project's schema.
    """
    title = _safe_str(data.get("name") or data.get("original_name"))
    original_title = _safe_str(data.get("original_name")) or title

    poster_path = data.get("poster_path")
    backdrop_path = data.get("backdrop_path")

    raw_genres = data.get("genres") or []
    genres = []
    for g in raw_genres:
        if isinstance(g, dict):
            name = g.get("name")
            if name:
                genres.append(str(name))
        elif isinstance(g, str):
            genres.append(g)

    return {
        "tmdb_id": _safe_int(data.get("id")),
        "title": title,
        "original_title": original_title,
        "overview": _safe_str(data.get("overview")),
        "poster_path": poster_path or None,
        "poster_url": get_poster_url(poster_path),
        "backdrop_path": backdrop_path or None,
        "backdrop_url": get_backdrop_url(backdrop_path),
        "first_air_date": data.get("first_air_date") or None,
        "genres": genres,
        "rating": _safe_float(data.get("vote_average")),
        "vote_count": _safe_int(data.get("vote_count")),
        "popularity": _safe_float(data.get("popularity")),
    }


# ==============================
# PUBLIC API
# ==============================

async def search_tv(
    query: str,
    page: int = 1,
    language: str = "en-US",
) -> list[dict]:
    """
    Search TMDB for TV shows.

    Returns a list of normalized result dicts.
    Returns [] on any failure (empty query, API error, timeout).
    """
    if not query or not isinstance(query, str):
        return []

    query = query.strip()

    if not query:
        return []

    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1

    data = await _tmdb_get(
        "/search/tv",
        params={
            "query": query,
            "page": page,
            "language": language,
            "include_adult": "false",
        },
    )

    if not data or not isinstance(data, dict):
        return []

    raw_results = data.get("results") or []

    if not isinstance(raw_results, list):
        return []

    normalized = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            normalized.append(_normalize_search_item(item))
        except Exception as e:
            logger.debug("Skipping malformed TMDB search item: %s", e)

    return normalized


async def get_tv_details(
    tmdb_id: int,
    language: str = "en-US",
) -> dict | None:
    """
    Fetch details for a single TMDB TV show.

    Returns a normalized dict, or None on failure.
    """
    try:
        tmdb_id = int(tmdb_id)
    except (TypeError, ValueError):
        return None

    if tmdb_id <= 0:
        return None

    data = await _tmdb_get(
        f"/tv/{tmdb_id}",
        params={"language": language},
    )

    if not data or not isinstance(data, dict):
        return None

    try:
        return _normalize_details(data)
    except Exception as e:
        logger.warning("Failed to normalize TMDB details: %s", e)
        return None


async def find_best_match(
    query: str,
    language: str = "en-US",
) -> dict | None:
    """
    Convenience helper:
        search_tv(query) → first result → get_tv_details(id)

    Returns the detailed normalized dict, or None.

    NOTE: The first TMDB search result is NOT guaranteed to be the
    correct anime/match. Callers must treat this as best-effort.
    """
    results = await search_tv(query, page=1, language=language)

    if not results:
        return None

    first = results[0]
    tmdb_id = first.get("tmdb_id")

    if not tmdb_id:
        return None

    details = await get_tv_details(tmdb_id, language=language)

    # Fall back to search-result data if details failed
    return details or first
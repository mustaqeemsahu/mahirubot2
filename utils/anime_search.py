# ==============================
# ANIME SEARCH ENGINE
# ==============================
# Shared fuzzy/exact search engine for all anime-search commands:
#   /anime  /search  /btn  direct_search
#
# Uses RapidFuzz for typo tolerance. Exact matches always win.
# No database access here — callers pass the anime list.
# ==============================

import re
import logging

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# ==============================
# CONFIDENCE THRESHOLDS
# ==============================

# Fuzzy match quality tiers (for the command-search engine)
FUZZY_DIRECT_THRESHOLD = 90        # very strong → return directly
FUZZY_STRONG_THRESHOLD = 82        # strong → return if clearly unique
FUZZY_SUGGEST_THRESHOLD = 72       # possible → suggest via buttons

# Short-query safety (very short strings fuzzy-match too easily)
SHORT_QUERY_LENGTH = 3             # <= this length → require very high score
SHORT_QUERY_MIN_SCORE = 95

# Ambiguity guard — if two candidates are this close, ask the user
AMBIGUITY_GAP = 3                  # top-2 score gap below this → ambiguous

# Whole-message direct match (for direct_search auto-reply)
DIRECT_FUZZY_THRESHOLD = 85
DIRECT_SHORT_QUERY_MIN_SCORE = 95


# ==============================
# NORMALIZATION
# ==============================

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_SPACE_RE = re.compile(r"\s+")


def normalize_anime_query(text: str) -> str:
    """
    Strong normalized form for fuzzy comparison:
      - lowercase
      - '-' and '_' → space
      - punctuation removed
      - multiple spaces collapsed
    """
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("-", " ").replace("_", " ")
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text)
    return text.strip()


def compact_normalize(text: str) -> str:
    """Normalized form without spaces. 'One Piece' → 'onepiece'."""
    return normalize_anime_query(text).replace(" ", "")


# ==============================
# CANDIDATE INDEX
# ==============================

def build_candidates(anime_list):
    """
    Build a list of candidate dicts from the anime database.

    Each anime produces one entry per unique normalized candidate form:
      { "anime": <ref>, "form": <normalized string>, "compact": <nospace>, "source": "name"|"key" }
    """
    candidates = []
    seen = set()

    for anime in anime_list:
        name = anime.get("name", "") or ""
        keys = anime.get("keys", []) or []

        raw_forms = [(name, "name")] + [(k, "key") for k in keys if k]

        for raw, source in raw_forms:
            form = normalize_anime_query(raw)
            if not form:
                continue

            key = (form, anime.get("name"))
            if key in seen:
                continue
            seen.add(key)

            candidates.append({
                "anime": anime,
                "form": form,
                "compact": compact_normalize(raw),
                "source": source,
            })

    return candidates


# ==============================
# EXACT MATCH
# ==============================

def exact_match(query, anime_list):
    """Exact name, exact key, normalized-exact, compact-exact."""
    q = normalize_anime_query(query)
    qc = compact_normalize(query)

    if not q:
        return []

    hits = []
    seen = set()

    for anime in anime_list:
        name = anime.get("name", "") or ""
        keys = anime.get("keys", []) or []

        n = normalize_anime_query(name)
        nc = compact_normalize(name)

        matched = False

        # Exact name (raw)
        if str(name).strip().lower() == str(query).strip().lower():
            matched = True
        # Exact key
        elif any(str(k).strip().lower() == str(query).strip().lower() for k in keys):
            matched = True
        # Normalized exact name
        elif n and q == n:
            matched = True
        # Normalized exact key
        elif any(normalize_anime_query(k) == q for k in keys):
            matched = True
        # Compact exact
        elif nc and qc and nc == qc:
            matched = True
        elif any(compact_normalize(k) == qc for k in keys if qc):
            matched = True

        if matched and anime.get("name") not in seen:
            hits.append(anime)
            seen.add(anime.get("name"))

    return hits


# ==============================
# PARTIAL MATCH (used by /search, /btn, /anime)
# ==============================

def partial_match(query, anime_list, limit=5):
    """
    Substring match on normalized forms.
    Preserves longest-match-first ranking.
    """
    q = normalize_anime_query(query)
    if not q:
        return []

    hits = []
    for anime in anime_list:
        name = anime.get("name", "") or ""
        keys = anime.get("keys", []) or []

        best_len = 0

        for raw in [name] + list(keys):
            form = normalize_anime_query(raw)
            if not form:
                continue
            if q in form or form in q:
                best_len = max(best_len, len(form))

        if best_len:
            hits.append((anime, best_len))

    hits.sort(key=lambda x: x[1], reverse=True)

    out = []
    seen = set()
    for anime, _ in hits:
        if anime.get("name") in seen:
            continue
        out.append(anime)
        seen.add(anime.get("name"))
        if len(out) >= limit:
            break
    return out


# ==============================
# FUZZY MATCH
# ==============================

def _score_against_candidate(query, qc, cand):
    """
    Return the best score for a query against one candidate.
    Uses WRatio + token_set_ratio + compact ratio.
    """
    scores = []

    try:
        scores.append(fuzz.WRatio(query, cand["form"]))
    except Exception:
        pass

    try:
        scores.append(fuzz.token_set_ratio(query, cand["form"]))
    except Exception:
        pass

    if qc and cand["compact"]:
        try:
            scores.append(fuzz.ratio(qc, cand["compact"]))
        except Exception:
            pass

    return max(scores) if scores else 0


def fuzzy_match(query, anime_list, limit=5):
    """
    Rank anime by fuzzy score against all candidate forms.

    Returns list of {anime, score, source} sorted by score desc.
    Deduplicated so each anime appears once with its best score.
    """
    q = normalize_anime_query(query)
    qc = compact_normalize(query)

    if not q:
        return []

    candidates = build_candidates(anime_list)
    if not candidates:
        return []

    is_short = len(q) <= SHORT_QUERY_LENGTH

    best = {}  # anime name → (score, source)

    for cand in candidates:
        anime = cand["anime"]
        name = anime.get("name")
        if not name:
            continue

        score = _score_against_candidate(q, qc, cand)

        if is_short:
            if score < SHORT_QUERY_MIN_SCORE:
                continue

        prev = best.get(name)
        if prev is None or score > prev[0]:
            best[name] = (score, cand["source"])

    ranked = sorted(best.items(), key=lambda x: x[1][0], reverse=True)[:limit]

    by_name = {a.get("name"): a for a in anime_list}

    out = []
    for name, (score, source) in ranked:
        anime = by_name.get(name)
        if anime is None:
            continue
        out.append({"anime": anime, "score": score, "source": source})

    return out


# ==============================
# COMBINED SEARCH (command path)
# ==============================
# Used by /anime, /search, /btn — CAN return partial and fuzzy results
# because the user explicitly asked for a search.
# ==============================

def find_anime_matches(query, anime_list, limit=5):
    """
    Full search with priority:
       1. exact (name / key / normalized / compact)
       2. partial substring
       3. fuzzy

    Returns a dict:
       {
         "mode": "exact" | "partial" | "fuzzy" | "ambiguous" | "none",
         "matches": [anime, ...],
         "scores": {name: score, ...},
         "confidence": float,
       }
    """
    anime_list = anime_list or []

    # 1. Exact
    exact = exact_match(query, anime_list)
    if exact:
        return {
            "mode": "exact",
            "matches": exact,
            "scores": {},
            "confidence": 100.0,
        }

    # 2. Partial
    partial = partial_match(query, anime_list, limit=limit)
    if partial:
        return {
            "mode": "partial",
            "matches": partial,
            "scores": {},
            "confidence": 100.0,
        }

    # 3. Fuzzy
    fuzzy = fuzzy_match(query, anime_list, limit=limit)
    if not fuzzy:
        return {
            "mode": "none",
            "matches": [],
            "scores": {},
            "confidence": 0.0,
        }

    top_score = fuzzy[0]["score"]
    top_match = fuzzy[0]["anime"]

    # Ambiguity check
    if len(fuzzy) >= 2:
        gap = fuzzy[0]["score"] - fuzzy[1]["score"]
        if gap < AMBIGUITY_GAP and fuzzy[0]["score"] < FUZZY_DIRECT_THRESHOLD:
            return {
                "mode": "ambiguous",
                "matches": [f["anime"] for f in fuzzy],
                "scores": {f["anime"].get("name"): f["score"] for f in fuzzy},
                "confidence": top_score,
            }

    # Confident direct pick
    if top_score >= FUZZY_DIRECT_THRESHOLD:
        return {
            "mode": "fuzzy",
            "matches": [top_match],
            "scores": {top_match.get("name"): top_score},
            "confidence": top_score,
        }

    # Strong but check uniqueness
    if top_score >= FUZZY_STRONG_THRESHOLD:
        close = [
            f for f in fuzzy
            if f["score"] >= FUZZY_STRONG_THRESHOLD
            and (top_score - f["score"]) < AMBIGUITY_GAP
        ]
        if len(close) == 1:
            return {
                "mode": "fuzzy",
                "matches": [top_match],
                "scores": {top_match.get("name"): top_score},
                "confidence": top_score,
            }
        return {
            "mode": "ambiguous",
            "matches": [f["anime"] for f in close],
            "scores": {f["anime"].get("name"): f["score"] for f in close},
            "confidence": top_score,
        }

    # Possible — show suggestions
    if top_score >= FUZZY_SUGGEST_THRESHOLD:
        suggest = [f for f in fuzzy if f["score"] >= FUZZY_SUGGEST_THRESHOLD]
        return {
            "mode": "ambiguous",
            "matches": [f["anime"] for f in suggest],
            "scores": {f["anime"].get("name"): f["score"] for f in suggest},
            "confidence": top_score,
        }

    # Below threshold → no reliable match
    return {
        "mode": "none",
        "matches": [],
        "scores": {},
        "confidence": top_score,
    }


def find_best_anime_matches(query, anime_list, limit=5):
    """Alias for find_anime_matches (public helper used by handlers)."""
    return find_anime_matches(query, anime_list, limit=limit)


# ==============================
# WHOLE-MESSAGE DIRECT MATCH
# ==============================
# Used ONLY by handlers/search.py :: direct_search().
#
# The ENTIRE normalized message must match an anime name or alias.
# Exact → compact → fuzzy. NO substring, NO n-grams, NO phrase
# extraction. This is the ONLY matcher allowed for auto-replies.
# ==============================

def direct_whole_message_match(text, anime_list, limit=5):
    """
    Whole-message direct match against anime name / keys.

    Returns a dict:
        {
            "mode": "exact" | "compact" | "fuzzy" | "none",
            "matches": [anime, ...],
            "confidence": float,
        }
    """
    anime_list = anime_list or []

    whole = normalize_anime_query(text)
    whole_compact = compact_normalize(text)

    if not whole:
        return {"mode": "none", "matches": [], "confidence": 0.0}

    # ---------- 1. EXACT ----------
    exact = []
    for anime in anime_list:
        name = anime.get("name", "") or ""
        keys = anime.get("keys", []) or []

        if normalize_anime_query(name) == whole:
            exact.append(anime)
            continue

        if any(normalize_anime_query(k) == whole for k in keys):
            exact.append(anime)

    if exact:
        return {"mode": "exact", "matches": exact, "confidence": 100.0}

    # ---------- 2. COMPACT EXACT ----------
    compact_hits = []
    for anime in anime_list:
        name = anime.get("name", "") or ""
        keys = anime.get("keys", []) or []

        if compact_normalize(name) == whole_compact:
            compact_hits.append(anime)
            continue

        if any(compact_normalize(k) == whole_compact for k in keys):
            compact_hits.append(anime)

    if compact_hits:
        return {"mode": "compact", "matches": compact_hits, "confidence": 100.0}

    # ---------- 3. FUZZY WHOLE-MESSAGE ----------
    candidates = build_candidates(anime_list)
    if not candidates:
        return {"mode": "none", "matches": [], "confidence": 0.0}

    is_short = len(whole) <= SHORT_QUERY_LENGTH
    min_score = DIRECT_SHORT_QUERY_MIN_SCORE if is_short else DIRECT_FUZZY_THRESHOLD

    best = {}  # anime name → (score, anime)

    for cand in candidates:
        anime = cand["anime"]
        name = anime.get("name")
        if not name:
            continue

        try:
            score = _score_against_candidate(whole, whole_compact, cand)
        except Exception:
            continue

        if score < min_score:
            continue

        prev = best.get(name)
        if prev is None or score > prev[0]:
            best[name] = (score, anime)

    if not best:
        return {"mode": "none", "matches": [], "confidence": 0.0}

    ranked = sorted(best.values(), key=lambda x: x[0], reverse=True)[:limit]
    top_score = ranked[0][0]

    return {
        "mode": "fuzzy",
        "matches": [a for _, a in ranked],
        "confidence": top_score,
    }
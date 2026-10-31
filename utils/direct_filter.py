import re
import unicodedata


def normalize(text):
    """Normalize names and manually saved keywords."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.casefold()
    text = re.sub(r"[_\W]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def get_keywords(anime):
    """Return the anime name and its manually saved keywords."""
    name = anime.get("name", "")
    keys = anime.get("keys") or []

    if isinstance(keys, str):
        keys = keys.split(",")

    values = [name] + list(keys)

    return {
        normalized
        for value in values
        if (normalized := normalize(value))
    }


def search_anime(message, anime_list, limit=10):
    """
    Search anime using manually saved keywords.

    Priority:
    1. Exact anime name or keyword
    2. Keyword occurring as a complete phrase
    3. No match

    No fuzzy matching or automatically generated aliases.
    """

    query = normalize(message)

    if not query:
        return []

    exact = []
    partial = []

    padded_query = f" {query} "

    for anime in anime_list:
        keywords = get_keywords(anime)

        if not keywords:
            continue

        # Exact name or keyword match
        if query in keywords:
            exact.append(anime)
            continue

        # Complete phrase match
        matching = [
            key for key in keywords
            if f" {key} " in padded_query
        ]

        if matching:
            longest = max(len(key) for key in matching)
            partial.append((longest, anime))

    # Exact matches always take priority
    if exact:
        return exact[:limit]

    # Longer matching keywords take priority
    partial.sort(key=lambda item: item[0], reverse=True)

    return [anime for _, anime in partial[:limit]]


def available_languages(anime):
    languages = {}

    for language in ("hindi", "english"):
        value = anime.get(f"{language}_link")

        if not isinstance(value, str):
            continue

        value = value.strip()

        if value and value != "-":
            languages[language] = value

    return languages

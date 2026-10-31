"""Single-line owner/sudo anime addition."""
from urllib.parse import urlsplit
from telegram.ext import CommandHandler
from database.mongo import get_all_anime, add_anime_db
from utils.direct_filter import normalize
from utils.sudo import require_sudo


def valid_url(value):
    try:
        p = urlsplit(value)
        return (p.scheme in ('https', 'http') and bool(p.hostname)
                and not p.username and not p.password
                and not any(c.isspace() for c in value) and len(value) <= 2048)
    except ValueError:
        return False


async def add_command(update, context):
    if not await require_sudo(update, context):
        return
    raw = update.message.text.partition(' ')[2].strip()
    parts = [part.strip() for part in raw.split('|')]
    usage = ('Usage:\n/add Name | keyword1, keyword2 | Sticker ID | Hindi Link | English Link\n'
             'Use - for a missing language link.')
    if len(parts) != 5:
        await update.message.reply_text(usage)
        return
    name, raw_keys, sticker, hindi, english = parts
    keys = list(dict.fromkeys(normalize(k) for k in raw_keys.split(',') if normalize(k)))
    if not name or len(name) > 200 or not (1 <= len(keys) <= 30) or any(len(k) > 100 for k in keys):
        await update.message.reply_text('Invalid name or keywords (1–30 keywords, max 100 characters each).')
        return
    if not sticker or sticker == '-' or len(sticker) > 512:
        await update.message.reply_text('Provide a valid sticker file ID.')
        return
    if hindi != '-' and not valid_url(hindi) or english != '-' and not valid_url(english):
        await update.message.reply_text('Links must be valid http(s) URLs or -.')
        return
    if hindi == '-' and english == '-':
        await update.message.reply_text('Provide at least one watch link.')
        return
    existing = await get_all_anime()
    terms = set(keys) | {normalize(name)}
    for anime in existing:
        old_keys = anime.get('keys') or []
        if isinstance(old_keys, str):
            old_keys = old_keys.split(',')
        old_terms = {normalize(x) for x in [anime.get('name', '')] + list(old_keys) if normalize(x)}
        if terms & old_terms:
            await update.message.reply_text('Anime name or keyword already exists: ' + str(anime.get('name', 'Unknown')))
            return
    try:
        await context.bot.get_file(sticker)
        await add_anime_db(name=name, keys=keys, sticker=sticker,
                           hindi_link=None if hindi == '-' else hindi,
                           english_link=None if english == '-' else english)
    except Exception:
        await update.message.reply_text('Sticker verification or database save failed. Check the sticker ID and bot logs.')
        return
    await update.message.reply_text(f'✅ Saved: {name}\nKeywords: {", ".join(keys)}\nHindi: {"Yes" if hindi != "-" else "No"} | English: {"Yes" if english != "-" else "No"}')


anime_add_handler = CommandHandler('add', add_command)

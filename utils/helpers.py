# ==============================
# HELPERS
# ==============================

import asyncio
from datetime import datetime

# Time function
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Auto delete message
async def auto_delete(message, delay=10):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

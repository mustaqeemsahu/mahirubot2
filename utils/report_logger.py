"""Utilities for sending bot reports to every configured report group."""

from config import REPORT_GROUP_ID


async def send_report(bot, text: str, **kwargs):
    group_ids = (
        REPORT_GROUP_ID
        if isinstance(REPORT_GROUP_ID, (list, tuple, set))
        else [REPORT_GROUP_ID]
    )

    for group_id in group_ids:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=text,
                **kwargs
            )
        except Exception as exc:
            print(f"[REPORT_LOGGER] Failed for {group_id}: {exc}")

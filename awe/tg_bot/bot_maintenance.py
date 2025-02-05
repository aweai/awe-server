from awe.maintenance import is_in_maintenance
from telegram import Update
from telegram.ext import ContextTypes

async def check_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_in_maintenance():
        if update.effective_chat is not None:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="System in maintenance. Please try again later.")
        return False

    return True

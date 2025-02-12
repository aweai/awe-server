from telegram import Update
from telegram.ext import ContextTypes
from .bot_maintenance import check_maintenance
import logging
from .base_handler import BaseHandler

class ResetHandler(BaseHandler):

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        await self.awe_agent.clear_message_for_user(user_id)
        await context.bot.send_message(update.effective_chat.id, "Chat history is cleared!")

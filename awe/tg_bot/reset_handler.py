from telegram import Update
from telegram.ext import ContextTypes
from .limit_handler import LimitHandler

class ResetHandler(LimitHandler):

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        tg_user_id = self.get_tg_user_id_from_update(update)

        if tg_user_id is None:
            await context.bot.send_message(update.effective_chat.id, "User ID Not found")
            return

        await self.aweAgent.clear_message_for_user(tg_user_id)
        await context.bot.send_message(update.effective_chat.id, "Chat history is cleared!")

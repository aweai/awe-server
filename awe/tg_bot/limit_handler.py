from typing import Optional
from awe.models.tg_bot import TGBot
from awe.agent_manager.user_agent import AweAgent
from telegram import Update

class LimitHandler:
    def __init__(self, user_agent_id: int, tg_bot_config: TGBot, aweAgent: AweAgent):
        self.user_agent_id = user_agent_id
        self.tg_bot_config = tg_bot_config
        self.aweAgent = aweAgent

    def get_tg_user_id_from_update(self, update: Update) -> Optional[str]:
        if update.effective_user is None:
            update.message.reply_text("User ID not found")
            return None

        user_id = str(update.effective_user.id)

        if user_id is None or user_id == "":
            update.message.reply_text("User ID not found")
            return None

        return user_id

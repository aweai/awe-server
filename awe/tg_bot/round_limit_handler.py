from .limit_handler import LimitHandler
from awe.models import UserAgentUserInvocations, UserAgentData
from telegram import Update
from telegram.ext import ContextTypes
import asyncio

class RoundLimitHandler(LimitHandler):

    async def check_round_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:

        if self.aweAgent.config.awe_token_config.max_invocation_per_round == 0:
            return True

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return False

        user_agent_data = await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
        user_invocation = await asyncio.to_thread(UserAgentUserInvocations.get_user_invocation, self.user_agent_id, user_id)

        if user_invocation is None:
            # Not invocation yet
            return True

        if user_invocation.current_round == user_agent_data.current_round \
            and user_invocation.round_invocations >= self.aweAgent.config.awe_token_config.max_invocation_per_round:

            update.message.reply_text("You have reached the invocation limit of this round. Please wait for the next round.")
            return False

        return True

    async def get_round_chances(self, update: Update) -> int:

        if self.aweAgent.config.awe_token_config.max_invocation_per_round == 0:
            return 0

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return 0

        user_agent_data = await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
        user_invocation = await asyncio.to_thread(UserAgentUserInvocations.get_user_invocation, self.user_agent_id, user_id)

        if user_invocation is None or user_invocation.current_round != user_agent_data.current_round:
            return self.aweAgent.config.awe_token_config.max_invocation_per_round
        else:
            return self.aweAgent.config.awe_token_config.max_invocation_per_round - user_invocation.round_invocations

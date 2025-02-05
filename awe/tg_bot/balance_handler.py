from telegram import Update
from telegram.ext import ContextTypes
from awe.models import TGBotUserWallet
from awe.blockchain import awe_on_chain
import asyncio
from .bot_maintenance import check_maintenance

class BalanceHandler:

    def __init__(self, user_agent_id: int):
        self.user_agent_id = user_agent_id

    def run_until_complete(self, address: str) -> str:
        balance = awe_on_chain.get_balance(address)
        return awe_on_chain.token_ui_amount(balance)

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None:
            update.message.reply_text("User ID not found")
            return

        user_id = str(update.effective_user.id)

        if user_id is None or user_id == "":
            update.message.reply_text("User ID not found")
            return

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

        if user_wallet is None or user_wallet.address is None or user_wallet.address == "":
            text = "You didn't bind your Solana wallet yet. Use /wallet command to bind your wallet."
            await context.bot.send_message(update.effective_chat.id, text)
            return

        awe_balance_ui = await asyncio.to_thread(self.run_until_complete, user_wallet.address)

        await context.bot.send_message(update.effective_chat.id, f"Your balance is {awe_balance_ui}")

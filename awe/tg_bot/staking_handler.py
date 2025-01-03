from .payment_limit_handler import PaymentLimitHandler
from telegram import Update
from telegram.ext import ContextTypes
import logging
import asyncio
from awe.models import UserStaking
from awe.models.utils import unix_timestamp_in_seconds
from datetime import datetime
from awe.settings import settings
import prettytable
from awe.blockchain import awe_on_chain

class StakingHandler(PaymentLimitHandler):

    def __init__(self, user_agent_id, tg_bot_config, aweAgent):
        super().__init__(user_agent_id, tg_bot_config, aweAgent)
        self.logger = logging.getLogger("[StakingHandler]")

    async def staking_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if len(context.args) == 0:
            await self.list_staking(update, context)
        elif len(context.args) == 2:
            action = context.args[0]
            if action == "add":
                await self.add_staking(update, context)
            elif action == "release":
                await self.release_staking(update, context)
            else:
                await context.bot.send_message(update.effective_chat.id, self.get_usage_text())
        else:
            await context.bot.send_message(update.effective_chat.id, self.get_usage_text())


    async def list_staking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        tg_user_id = self.get_tg_user_id_from_update(update)
        if tg_user_id is None:
            return

        staking_list = await asyncio.to_thread(UserStaking.get_user_staking_list, self.user_agent_id, tg_user_id)

        if len(staking_list) == 0:
            msg = "You have no staking yet.\n\n"
        else:
            msg = "Here's your staking data:\n\n"

            table = prettytable.PrettyTable(["ID", "Staking", "Staked at", "Locked until"])

            for staking_item in staking_list:
                dt = datetime.fromtimestamp(staking_item.created_at)
                dt_str = dt.strftime("%Y-%m-%d")
                rt = datetime.fromtimestamp(staking_item.created_at + settings.tn_user_staking_locking_days * 86400)
                rt_str = rt.strftime("%Y-%m-%d")
                table.add_row([staking_item.id, f"{staking_item.amount}.00", dt_str, rt_str])

            msg = msg + f"<pre>{table}</pre>\n\n"

        msg = msg + self.get_usage_text()
        await context.bot.send_message(update.effective_chat.id, msg, parse_mode="HTML")

    async def add_staking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            amount = int(context.args[1])
        except:
            await context.bot.send_message(update.effective_chat.id, "Invalid amount provided.")

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return

        user_wallet = await self.check_wallet(update, context, False)

        if user_wallet is None:
            return

        if not await self.check_user_balance(user_wallet.address, amount, update, context):
            return

        # Send the approve buttons
        reply_markup = await self.get_approve_buttons("user_staking", user_id, user_wallet, amount)

        await context.bot.send_message(
            update.effective_chat.id,
            "Please use the buttons below to approve the transaction",
            reply_markup=reply_markup)

    async def release_staking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            staking_id = int(context.args[1])
        except:
            await context.bot.send_message(update.effective_chat.id, "Invalid ID provided")

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return

        user_staking = await asyncio.to_thread(UserStaking.get_user_staking, staking_id, self.user_agent_id, user_id)

        if user_staking is None:
            await context.bot.send_message(update.effective_chat.id, "Invalid ID provided")
            return

        now = unix_timestamp_in_seconds()
        if now - user_staking.created_at < settings.tn_user_staking_locking_days * 86400:
            await context.bot.send_message(update.effective_chat.id, "Staking is still locked!")
            return

        user_wallet = await self.check_wallet(update, context, False)

        if user_wallet is None:
            return

        try:
            tx = await asyncio.to_thread(
                self.return_user_staking,
                staking_id,
                user_staking.amount,
                user_wallet.address,
                self.user_agent_id,
                user_id
            )

            msg = "Your staking has been returned!\n\n" + tx
            await context.bot.send_message(update.effective_chat.id, msg)

        except Exception as e:
            self.logger.error(e)
            await context.bot.send_message(update.effective_chat.id, "Error release the staking. Please try again later.")


    def return_user_staking(self, staking_id: int, amount: int, wallet_address: str, user_agent_id: int, tg_user_id: str) -> str:

        self.logger.info(f"[{staking_id}] Releasing user staking")

        # Update the staking status
        UserStaking.release_user_staking(staking_id, user_agent_id, tg_user_id)

        self.logger.info(f"[{staking_id}] Staking status updated")

        # Send the transaction
        tx = awe_on_chain.transfer_to_user(wallet_address, amount)

        self.logger.info(f"[{staking_id}] Release staking tx sent: {tx}")

        # Record the tx
        UserStaking.record_releasing_user_staking_tx(staking_id, user_agent_id, tg_user_id, tx)

        return tx

    def get_usage_text(self) -> str:
        usage = "Command usage:\n\n"
        usage = usage + "/staking - List your current staking\n"
        usage = usage + "/staking add {amount} - Add staking\n"
        usage = usage + "/staking release {id} - Release staking"

        return usage
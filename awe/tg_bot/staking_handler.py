from .payment_limit_handler import PaymentLimitHandler
from telegram import Update
from telegram.ext import ContextTypes
import logging
import asyncio
from awe.models import UserStaking
from datetime import datetime
from awe.settings import settings
import prettytable
from awe.agent_manager.agent_fund import release_user_staking, ReleaseStakingNotAllowedException
import time

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

        locking_till = int(time.time()) + settings.tn_agent_staking_locking_days * 86400
        locking_datetime = datetime.fromtimestamp(locking_till)
        locking_till_str = locking_datetime.strftime("%Y-%m-%d")

        await context.bot.send_message(
            update.effective_chat.id,
            f"{amount}.00 $AWE will be transferred to the system account for staking. You won't be able to get them back until {locking_till_str}. Please use the buttons below to approve the transaction:",
            reply_markup=reply_markup)

    async def release_staking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        try:
            staking_id = int(context.args[1])
        except:
            await context.bot.send_message(update.effective_chat.id, "Invalid ID provided")

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return

        user_wallet = await self.check_wallet(update, context, False)

        if user_wallet is None:
            return

        try:
            tx = await asyncio.to_thread(release_user_staking, self.user_agent_id, user_id, staking_id, user_wallet.address)

            msg = f"Your staking has been returned!\n\n{tx}"
            await context.bot.send_message(update.effective_chat.id, msg)

        except ReleaseStakingNotAllowedException as e:
            await context.bot.send_message(update.effective_chat.id, str(e))
        except Exception as e:
            self.logger.error(e)
            await context.bot.send_message(update.effective_chat.id, "Error release the staking. Please try again later.")


    def get_usage_text(self) -> str:
        usage = "Command usage:\n\n"
        usage = usage + "/staking - List your current staking\n"
        usage = usage + "/staking add {amount} - Add staking\n"
        usage = usage + "/staking release {id} - Release staking"

        return usage

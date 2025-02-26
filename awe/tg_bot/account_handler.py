from telegram import Update
from telegram.ext import ContextTypes
from awe.models import TGBotUserWallet
from awe.blockchain import awe_on_chain
import asyncio
from .bot_maintenance import check_maintenance
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from awe.models import TgUserAccount
from awe.blockchain.phantom import get_connect_url, get_browser_connect_url
from awe.blockchain import awe_on_chain
import asyncio
from .bot_maintenance import check_maintenance
from typing import Optional
from awe.settings import settings
from awe.blockchain.phantom import get_connect_url, get_approve_url, get_browser_connect_url, get_browser_approve_url
from .base_handler import BaseHandler
import logging
from awe.agent_manager.agent_fund import withdraw_to_user, WithdrawNotAllowedException


logger = logging.getLogger("[AccountHandler]")

class AccountHandler(BaseHandler):

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        user_balance, user_rewards = await asyncio.to_thread(TgUserAccount.get_balance, user_id)

        if user_rewards == 0:
            await context.bot.send_message(update.effective_chat.id, f"Your balance is $AWE {user_balance}.00")
        else:
            await context.bot.send_message(update.effective_chat.id, f"Your balance is $AWE {user_balance + user_rewards}.00 ({user_rewards}.00 can not be withdrew)")


    async def deposit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        if len(context.args) != 1:
            await update.message.reply_text("Command usage: /deposit <amount>")

        try:
            amount = int(context.args[0])
        except:
            await update.message.reply_text("Invalid amount provided")
            return

        if amount < settings.min_player_deposit_amount:
            await update.message.reply_text(f"Minimum deposit amount: $AWE {settings.min_player_deposit_amount}")
            return

        user_wallet = await self.check_wallet(update, context)

        if user_wallet is None:
            return

        if not await self.check_wallet_balance(user_wallet.address, amount, update, context):
            return

        # Send the deposit button
        reply_markup = await self.get_approve_buttons(
            "user_payment",
            user_id,
            user_wallet,
            amount
        )

        msg = f"Deposit $AWE {amount}.00 into your account. It could be used across all Memegents on Awe!\n\n"
        msg = msg + "Click the button below to start the deposit."
        await update.message.reply_text(msg, reply_markup=reply_markup)


    async def withraw_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_maintenance(update, context):
            return
        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        if len(context.args) != 1:
            await update.message.reply_text(f"Command usage: /withdraw <amount>\n\n(A tx fee of $AWE {settings.withdraw_tx_fee} will be charged)")

        try:
            amount = int(context.args[0])
        except:
            await update.message.reply_text("Invalid amount provided")
            return

        if amount < settings.min_player_withdraw_amount:
            await update.message.reply_text(f"Minimum withdraw amount: $AWE {settings.min_player_withdraw_amount}\n\n(A tx fee of $AWE {settings.withdraw_tx_fee} will be charged)")
            return

        user_wallet = await self.check_wallet(update, context)

        if user_wallet is None:
            return

        try:
            tx = await asyncio.to_thread(withdraw_to_user, self.user_agent_id, user_id, user_wallet.address, amount)
        except WithdrawNotAllowedException as we:
            await context.bot.send_message(update.effective_chat.id, str(we))
            return
        except Exception as e:
            logger.error(e)
            await context.bot.send_message(update.effective_chat.id, "Something is wrong. Please try again later.")
            return

        await context.bot.send_message(update.effective_chat.id, f"$AWE {amount}.00 has been transferred to your wallet {user_wallet.address}. The transaction should be confirmed in a short while:\n\n{tx}")


    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, user_id)

        if user_wallet is None or user_wallet.address is None or user_wallet.address == "":
            text = "You didn't bind your Solana wallet yet. Click the button below to bind your Solana wallet."
        else:
            text = f"Your Solana wallet address is {user_wallet.address}. Click the button below to bind a new wallet."

        keyboard = [
            [InlineKeyboardButton("Phantom Mobile", url=get_connect_url(self.user_agent_id, user_id))],
            [InlineKeyboardButton("Browser Wallets", url=get_browser_connect_url(self.user_agent_id, user_id, self.tg_bot_config.username))],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)


    async def check_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[TGBotUserWallet]:

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, user_id)

        if user_wallet is None \
            or user_wallet.address is None or user_wallet.address == "":

            text = "You must bind your Solana wallet first. Click the button below to bind your wallet."
            mobile_connect_url = await asyncio.to_thread(get_connect_url, self.user_agent_id, user_id)
            browser_connect_url = await asyncio.to_thread(get_browser_connect_url, self.user_agent_id, user_id, self.tg_bot_config.username)
            keyboard = [
                [InlineKeyboardButton("Phantom Mobile", url=mobile_connect_url)],
                [InlineKeyboardButton("Browser Wallets", url=browser_connect_url)],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)

            return None

        return user_wallet


    async def check_wallet_balance(self, address: str, minimum: int, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        # Check the user balance
        user_balance = await asyncio.to_thread(awe_on_chain.get_balance, address)
        user_balance_int = int(user_balance / 1e9)

        logger.debug(f"User balance: {user_balance_int}.00")

        if user_balance_int < minimum:

            msg = f"You don't have enough $AWE to pay ({address}: {user_balance_int}.00)."
            if minimum > 0:
                msg = msg + f"Transfer {minimum}.00 $AWE to your wallet to begin."
            else:
                msg = msg + f"Transfer some $AWE to your wallet to begin."

            await update.message.reply_text(msg)

            return False

        return True


    async def get_approve_buttons(
            self,
            action: str,
            tg_user_id: str,
            user_wallet: TGBotUserWallet,
            amount: int
        ) -> InlineKeyboardMarkup:

        keyboard = []

        if user_wallet.phantom_encryption_public_key is not None \
            and user_wallet.phantom_encryption_public_key!= "" \
            and user_wallet.phantom_session is not None \
            and user_wallet.phantom_session != "":

            approve_url = await asyncio.to_thread(
                get_approve_url,
                action,
                self.user_agent_id,
                tg_user_id,
                amount,
                user_wallet.address,
                user_wallet.phantom_session,
                user_wallet.phantom_encryption_public_key
            )

            keyboard.append([InlineKeyboardButton(f"Phantom Mobile", url=approve_url)])
        else:
            browser_approve_url = await asyncio.to_thread(
                get_browser_approve_url,
                action,
                self.user_agent_id,
                tg_user_id,
                user_wallet.address,
                amount,
                self.tg_bot_config.username
            )

            keyboard.append([InlineKeyboardButton(f"Browser Wallets", url=browser_approve_url)])

        return InlineKeyboardMarkup(keyboard)

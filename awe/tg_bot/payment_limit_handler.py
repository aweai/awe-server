from .limit_handler import LimitHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from awe.models import TGBotUserWallet, TgUserDeposit, UserAgentUserInvocations
from awe.blockchain.phantom import get_connect_url, get_approve_url, get_browser_connect_url, get_browser_approve_url
from typing import Optional
from awe.blockchain import awe_on_chain
import asyncio
import logging

class PaymentLimitHandler(LimitHandler):

    def __init__(self, user_agent_id, tg_bot_config, aweAgent):
        super().__init__(user_agent_id, tg_bot_config, aweAgent)
        self.logger = logging.getLogger("[PaymentLimitHandler]")

    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

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

    async def check_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE, is_group_chat: bool) -> Optional[TGBotUserWallet]:
            user_id = self.get_tg_user_id_from_update(update)
            if user_id is None:
                return None

            user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

            if user_wallet is None \
                or user_wallet.address is None or user_wallet.address == "":

                if not is_group_chat:
                    text = "You must bind your Solana wallet first. Click the button below to bind your wallet."
                    mobile_connect_url = await asyncio.to_thread(get_connect_url, self.user_agent_id, user_id)
                    browser_connect_url = await asyncio.to_thread(get_browser_connect_url, self.user_agent_id, user_id, self.tg_bot_config.username)
                    keyboard = [
                        [InlineKeyboardButton("Phantom Mobile", url=mobile_connect_url)],
                        [InlineKeyboardButton("Browser Wallets", url=browser_connect_url)],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(text, reply_markup=reply_markup)
                else:
                    text = "Please DM me to bind your wallet first."
                    await update.message.reply_text(text)

                return None

            return user_wallet

    async def check_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, is_group_chat: bool) -> bool:

        user_wallet = await self.check_wallet(update, context, is_group_chat)
        if user_wallet is None:
            return False

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return False

        tg_user_deposit = await asyncio.to_thread(TgUserDeposit.get_user_deposit_for_latest_round, self.user_agent_id, user_id)
        if tg_user_deposit is None:

            self.logger.debug("User not paid.")

            if not is_group_chat:
                await self.ask_for_payment(update, context, user_id, user_wallet)
            else:
                await update.message.reply_text(f"Please DM me to pay first.")

            return False

        else:
            # Check invocation limit for this payment
            if self.aweAgent.config.awe_token_config.max_invocation_per_payment != 0:

                user_invocation = await asyncio.to_thread(UserAgentUserInvocations.get_user_invocation, self.user_agent_id, user_id)

                if user_invocation is None:
                    # Not invocation yet
                    return True

                if user_invocation.payment_invocations >= self.aweAgent.config.awe_token_config.max_invocation_per_payment:

                    if not is_group_chat:
                        await self.ask_for_payment(update, context, user_id, user_wallet)
                    else:
                        await update.message.reply_text(f"Please DM me to pay first.")

                    return False

        return True

    async def get_payment_chances(self, update:Update) -> int:

        user_id = self.get_tg_user_id_from_update(update)
        if user_id is None:
            return 0

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

        if user_wallet is None \
            or user_wallet.address is None or user_wallet.address == "":
            return 0

        tg_user_deposit = await asyncio.to_thread(TgUserDeposit.get_user_deposit_for_latest_round, self.user_agent_id, user_id)
        if tg_user_deposit is None:
            return 0

        user_invocation = await asyncio.to_thread(UserAgentUserInvocations.get_user_invocation, self.user_agent_id, user_id)

        if user_invocation is None:
            return self.aweAgent.config.awe_token_config.max_invocation_per_payment
        else:
            chances = self.aweAgent.config.awe_token_config.max_invocation_per_payment - user_invocation.payment_invocations

            if chances <= 0:
                return 0
            return chances

    async def check_user_balance(self, address: str, minimum: int, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        # Check the user balance
        user_balance = await asyncio.to_thread(awe_on_chain.get_balance, address)
        user_balance_int = int(user_balance / 1e9)

        self.logger.debug(f"User balance: {user_balance_int}.00")

        if user_balance_int < minimum:

            msg = f"You don't have enough AWE tokens to pay ({address}: {user_balance_int}.00)."
            if minimum > 0:
                msg = msg + f"Transfer {minimum}.00 AWE to your wallet to begin."
            else:
                msg = msg + f"Transfer some AWE to your wallet to begin."

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

    async def ask_for_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE, tg_user_id: str, user_wallet: TGBotUserWallet):
        price = self.aweAgent.config.awe_token_config.user_price
        self.logger.debug(f"Price of use agent is {price}. Checking user balance...")

        if not await self.check_user_balance(user_wallet.address, price, update, context):
            return

        # Send the deposit button
        reply_markup = await self.get_approve_buttons(
            "user_payment",
            tg_user_id,
            user_wallet,
            price
        )

        await update.message.reply_text(f"Pay AWE {price}.00 to use this Memegent.\n\nThe payment takes some time to confirm after you finish the process.\nUse /chances command to check if your limit has been reset.", reply_markup=reply_markup)

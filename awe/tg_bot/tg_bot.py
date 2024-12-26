import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from awe.awe_agent.awe_agent import AweAgent
from PIL import Image
import io
from pathlib import Path
import asyncio
from collections import deque
from ..models.tg_bot import TGBot as TGBotConfig
from ..models.tg_bot_user_wallet import TGBotUserWallet
from ..models.tg_user_deposit import TgUserDeposit
from awe.blockchain.phantom import get_connect_url, get_approve_url
from awe.blockchain import awe_on_chain
from typing import Optional

# Skip regular network logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

class TGBot:
    def __init__(self, agent: AweAgent, tg_bot_config: TGBotConfig, user_agent_id: int) -> None:

        self.logger = logging.getLogger(f"[TG Bot] [{user_agent_id}]")
        self.aweAgent = agent
        self.tg_bot_config = tg_bot_config
        self.user_agent_id = user_agent_id

        # TG Application
        self.logger.info("Initializing TG Bot...")
        self.application = ApplicationBuilder().token(tg_bot_config.token).build()

        # Start handler
        start_handler = CommandHandler('start', self.start_command)
        self.application.add_handler(start_handler)

        # Wallet handler
        wallet_handler = CommandHandler('wallet', self.wallet_command)
        self.application.add_handler(wallet_handler)

        # Message handler
        message_handler = MessageHandler(filters.UpdateType.MESSAGE & filters.TEXT & (~filters.COMMAND), self.respond_message)
        self.application.add_handler(message_handler)

        self.application.add_error_handler(self.error_handler)

        self.group_chat_contents = {}

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        start_message = self.tg_bot_config.start_message
        if start_message != "":
            await self.send_response({"text": start_message}, update, context)
        else:
            prompt = "This is the first time the user comes to you, give the user your best greeting"
            resp = await self.aweAgent.get_response(
                "[Private chat] " + prompt,
                context._user_id,
                f"{update.effective_chat.id}")
            await self.send_response(resp, update, context)

    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user is None:
            await self.send_response("User ID not found", update, context)
            return

        user_id = str(update.effective_user.id)

        if user_id is None or user_id == "":
            await self.send_response("User ID not found", update, context)
            return

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

        if user_wallet is None or user_wallet.address is None or user_wallet.address == "":
            text = "You didn't bind your Solana wallet yet. Click the button below to bind your Solana wallet."
        else:
            text = f"Your Solana wallet address is {user_wallet.address}. Click the button below to bind a new wallet."

        keyboard = [
            [InlineKeyboardButton("Phantom Wallet", url=get_connect_url(self.user_agent_id, user_id))],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

    async def check_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[TGBotUserWallet]:
        if update.effective_user is None:
            await self.send_response("User ID not found", update, context)
            return None

        user_id = str(update.effective_user.id)
        if user_id is None or user_id == "":
            await self.send_response("User ID not found", update, context)
            return None

        user_wallet = await asyncio.to_thread(TGBotUserWallet.get_user_wallet, self.user_agent_id, user_id)

        if user_wallet is None \
            or user_wallet.address is None or user_wallet.address == "" \
            or user_wallet.phantom_session is None or user_wallet.phantom_session == "" \
            or user_wallet.phantom_encryption_public_key is None or user_wallet.phantom_encryption_public_key == "":

            text = "You must bind your Solana wallet first. Click the button below to bind your wallet."
            keyboard = [
                [InlineKeyboardButton("Phantom Wallet", url=get_connect_url(self.user_agent_id, user_id))],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            return None

        return user_wallet

    async def check_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:

        user_wallet = await self.check_wallet(update, context)
        if user_wallet is None:
            return False

        user_id = str(update.effective_user.id)
        tg_user_deposit = await asyncio.to_thread(TgUserDeposit.get_user_deposit_for_latest_round, self.user_agent_id, user_id)
        if tg_user_deposit is None:
            self.logger.debug("User not paid.")
            price = self.aweAgent.config.awe_token_config.user_price
            self.logger.debug(f"Price of use agent is {price}. Checking user balance...")

            # Check the user balance
            user_balance = await asyncio.to_thread(awe_on_chain.get_balance, user_wallet.address)
            user_balance_int = int(user_balance / 1e9)

            self.logger.debug(f"User balance: {user_balance_int}.00")

            if user_balance_int < price:
                await update.message.reply_text(f"You don't have enough AWE tokens to pay ({user_wallet.address}: {user_balance_int}.00). Transfer {price}.00 AWE to your wallet to begin.")
                return False

            # Send the deposit button
            url = await asyncio.to_thread(get_approve_url, self.user_agent_id, user_id, price, user_wallet.address, user_wallet.phantom_session, user_wallet.phantom_encryption_public_key)
            keyboard = [
                [InlineKeyboardButton(f"Pay AWE {price}.00", url=url)],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Pay AWE {self.aweAgent.config.awe_token_config.user_price}.00 to start using this Memegent", reply_markup=reply_markup)
            return False

        return True


    def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.error("Exception while handling an update:", exc_info=context.error)

    def read_image_file(self, image_path: Path) -> bytes:
        image = Image.open(image_path)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG")
        return image_bytes.getvalue()

    def update_group_chat_history(self, message: str, chat_id: str):
        if chat_id not in self.group_chat_contents:
            self.group_chat_contents[chat_id] = deque()

        self.group_chat_contents[chat_id].append(message)

        if len(self.group_chat_contents[chat_id]) >= 10:
            self.group_chat_contents[chat_id].popleft()

    def get_group_chat_history(self, chat_id: str):
        if chat_id not in self.group_chat_contents:
            return ""
        return "\n".join(self.group_chat_contents[chat_id])

    async def respond_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user is None:
            await self.send_response("User ID not found", update, context)
            return

        user_id = str(update.effective_user.id)
        if user_id is None or user_id == "":
            await self.send_response("User ID not found", update, context)
            return

        resp = await self.aweAgent.get_response(
            "[Private chat] " + update.message.text,
            user_id,
            user_id)
        await self.send_response(resp, update, context)

    async def respond_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        bot_mentioned = False
        entities = update.effective_message.parse_entities(["mention"])
        for k in entities:
            if entities[k] == f"@{self.tg_bot_config.username}":
                bot_mentioned = True

        if update.effective_chat is None:
            await self.send_response("Chat ID not found", update, context)
            return

        chat_id = f"{update.effective_chat.id}"

        if bot_mentioned:

            if update.effective_user is None:
                await self.send_response("User ID not found", update, context)
                return

            user_id = str(update.effective_user.id)
            if user_id is None or user_id == "":
                await self.send_response("User ID not found", update, context)
                return

            history_messages = await asyncio.to_thread(self.get_group_chat_history, chat_id)

            resp = await self.aweAgent.get_response(
                "[Group chat] " + history_messages + "\n" + update.message.text,
                user_id
            )

            await self.send_response(resp, update, context)

        else:
            # Record last 5 messages in the channel for agent respond context
            user_text = update.message.text

            user_name = update.message.from_user.first_name
            if update.message.from_user.last_name is not None:
                user_name = user_name + " " + update.message.from_user.last_name

            message = f"{user_name}: {user_text}"

            await asyncio.to_thread(self.update_group_chat_history, message, chat_id)

    async def respond_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        # Check user deposit
        if self.aweAgent.config.awe_token_enabled:
            if not await self.check_deposit(update, context):
                return

        # Start chat
        if update.message.chat.type == constants.ChatType.PRIVATE:
            await self.respond_dm(update, context)
        elif update.message.chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
            await self.respond_group(update, context)

    async def send_response(self, resp: dict, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if 'image' in resp and resp["image"] is not None and resp["image"] != "":
            image_bytes = await asyncio.to_thread(self.read_image_file, resp["image"])
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)
        elif 'text' in resp and resp["text"] is not None and resp["text"] != "":
            await context.bot.send_message(chat_id=update.effective_chat.id, text=resp["text"])
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="My brain is messed up...try me again")

    def start(self) -> None:
        self.logger.info("Starting TG Bot...")
        self.application.run_polling()

import logging
from telegram import Update, constants
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from awe.awe_agent.awe_agent import AweAgent
from awe.models import UserAgentUserInvocations, TGUserDMChat
from PIL import Image
import io
from pathlib import Path
import asyncio
from ..models.tg_bot import TGBot as TGBotConfig
from .payment_handler import PaymentHandler
from .staking_handler import StakingHandler
from .help_command import help_command, get_help_message
from .account_handler import AccountHandler
from .power_command import power_command
from .reset_handler import ResetHandler
from pathlib import Path
from datetime import datetime
from awe.db import engine
from sqlmodel import Session, select
from typing import Optional
from threading import Thread
from awe.cache import cache
import json
from .bot_maintenance import check_maintenance
import time
import traceback


# Skip regular network logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Skip regular TG Bot logs
logging.getLogger("telegram.ext.Updater").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.ExtBot").setLevel(logging.WARNING)


class TGBot:
    def __init__(self, agent: AweAgent, tg_bot_config: TGBotConfig, user_agent_id: int) -> None:

        self.logger = logging.getLogger(f"[TG Bot] [{user_agent_id}]")
        self.awe_agent = agent
        self.tg_bot_config = tg_bot_config
        self.user_agent_id = user_agent_id

        # TG Application
        self.logger.info("Initializing TG Bot...")
        self.application = ApplicationBuilder().token(tg_bot_config.token).build()

        # Start handler
        start_handler = CommandHandler('start', self.start_command)
        self.application.add_handler(start_handler)

        # Payment handler
        self.payment_handler = PaymentHandler(self.user_agent_id, self.tg_bot_config, self.awe_agent)

        # Pay command
        pay_command_handler = CommandHandler("pay", self.payment_handler.pay_for_current_round)
        self.application.add_handler(pay_command_handler)

        # Chances command
        chances_handler = CommandHandler("chances", self.chances_command)
        self.application.add_handler(chances_handler)

        # Staking handler
        self.staking_handler = StakingHandler(self.user_agent_id, self.tg_bot_config, self.awe_agent)

        # Staking command
        staking_command_handler = CommandHandler("staking", self.staking_handler.staking_command)
        self.application.add_handler(staking_command_handler)

        # Account handler
        self.account_handler = AccountHandler(self.user_agent_id, self.tg_bot_config, self.awe_agent)

        balance_command_handler = CommandHandler("balance", self.account_handler.balance_command)
        self.application.add_handler(balance_command_handler)

        deposit_command_handler = CommandHandler("deposit", self.account_handler.deposit_command)
        self.application.add_handler(deposit_command_handler)

        withdraw_command_handler = CommandHandler("withdraw", self.account_handler.withraw_command)
        self.application.add_handler(withdraw_command_handler)

        wallet_command_handler = CommandHandler('wallet', self.account_handler.wallet_command)
        self.application.add_handler(wallet_command_handler)

        # Power command
        power_command_handler = CommandHandler("power", power_command)
        self.application.add_handler(power_command_handler)

        # Help command
        help_command_handler = CommandHandler("help", help_command)
        self.application.add_handler(help_command_handler)

        # Reset command
        self.reset_handler = ResetHandler(self.user_agent_id, self.tg_bot_config, self.awe_agent)
        reset_command_handler = CommandHandler("reset", self.reset_handler.reset_command)
        self.application.add_handler(reset_command_handler)

        # Message handler
        message_handler = MessageHandler(filters.UpdateType.MESSAGE & filters.TEXT & (~filters.COMMAND), self.respond_message)
        self.application.add_handler(message_handler)

        self.application.add_error_handler(self.error_handler)

        self.group_chat_contents = {}

        self.stopped = False


    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_user is None or update.effective_chat is None:
            return

        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)

        start_message = self.tg_bot_config.start_message

        help_message = get_help_message()

        await self.send_response({"text": start_message + "\n\n" + help_message}, update, context, False)
        await asyncio.to_thread(self.record_dm_chat_id, user_id, chat_id)


    async def chances_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.effective_chat is None or update.effective_user is None:
            return

        user_id = str(update.effective_user.id)

        invocation_chances, payment_chances = await self.payment_handler.get_chances(user_id)

        if invocation_chances == -1:
            msg = "This Memegent has no invocation limit."
        else:
            msg = f"{invocation_chances} messages left for this play."

            if self.awe_agent.config.awe_token_config.max_payment_per_round != 0:
                msg = msg + f"\n\n{payment_chances} payment chances left for this round."
            else:
                msg = msg + "\n\nReset by paying again."

        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


    def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.error("Exception while handling an update:", exc_info=context.error)


    def read_image_file(self, image_path: Path) -> bytes:
        image = Image.open(image_path)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="JPEG")
        return image_bytes.getvalue()


    async def check_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE, is_group_chat: bool) -> bool:

        if update.effective_user is None or update.effective_chat is None:
            return False

        user_id = str(update.effective_user.id)

        invocation_chances, payment_chances = await self.payment_handler.get_chances(user_id)

        if invocation_chances == 0:
            if payment_chances == 0:
                await update.message.reply_text("You have reached the limit of this round. Please wait for the next round.")
            elif is_group_chat:
                await update.message.reply_text(f"Please DM me to pay first.")
            else:
                await self.payment_handler.ask_for_payment(update, context)
            return False

        return True

    async def increase_invocation(self, tg_user_id: str):
        await asyncio.to_thread(UserAgentUserInvocations.add_invocation, self.user_agent_id, tg_user_id)


    async def respond_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user is None or update.effective_chat is None:
            return

        if not await self.check_limits(update, context, False):
            return

        user_id = str(update.effective_user.id)

        input = "[Private chat] " + update.message.text

        resp = await self.awe_agent.get_response(
            input,
            user_id,
            user_id)

        await self.send_response(resp, update, context, False)

        await self.increase_invocation(user_id)
        await asyncio.to_thread(self.log_interact, user_id, str(update.effective_chat.id), input, resp)


    async def respond_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user is None or update.effective_chat is None:
            return

        chat_id = f"{update.effective_chat.id}"
        user_id = f"{update.effective_user.id}"

        bot_mentioned = False
        entities = update.effective_message.parse_entities(["mention"])
        for k in entities:
            if entities[k] == f"@{self.tg_bot_config.username}":
                bot_mentioned = True

        # Record messages in the channel for agent respond context
        user_text = update.message.text

        user_name = update.message.from_user.first_name
        if update.message.from_user.last_name is not None:
            user_name = user_name + " " + update.message.from_user.last_name

        user_message = f"{user_name} (id: {update.effective_user.id}): {user_text}"

        if bot_mentioned:
            if not await self.check_limits(update, context, True):
                return

            resp = await self.awe_agent.get_response(
                user_message,
                user_id,
                chat_id
            )

            await self.send_response(resp, update, context, True)
            await self.increase_invocation(user_id)
            await asyncio.to_thread(self.log_interact, user_id, chat_id, user_message, resp)
        else:
            await self.awe_agent.add_message(
                user_message,
                user_id,
                chat_id
            )


    async def respond_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await check_maintenance(update, context):
            return

        if update.message.chat.type == constants.ChatType.PRIVATE:
            await self.respond_dm(update, context)
        elif update.message.chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
            await self.respond_group(update, context)

    async def send_response(self, resp: dict, update: Update, context: ContextTypes.DEFAULT_TYPE, reply: bool):
        if 'image' in resp and resp["image"] is not None and resp["image"] != "":
            image_bytes = await asyncio.to_thread(self.read_image_file, resp["image"])

            if reply:
                await update.message.reply_photo(photo=image_bytes)
            else:
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes)

        else:
            if 'text' in resp and resp["text"] is not None and resp["text"] != "":
                text = resp["text"]
            else:
                text = "My brain is messed up...try me again"

            if reply:
                await update.message.reply_text(text=text)
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


    def record_dm_chat_id(self, tg_user_id: str, dm_chat_id: str):
        with Session(engine) as session:
            statement = select(TGUserDMChat).where(
                TGUserDMChat.user_agent_id == self.user_agent_id,
                TGUserDMChat.tg_user_id == tg_user_id
            )
            user_dm_chat = session.exec(statement).first()

            if user_dm_chat is None:
                user_dm_chat = TGUserDMChat(
                    user_agent_id=self.user_agent_id,
                    tg_user_id=tg_user_id,
                    chat_id=dm_chat_id
                )
            else:
                user_dm_chat.chat_id = dm_chat_id

            session.add(user_dm_chat)
            session.commit()


    def get_dm_chat_id(self, tg_user_id: str) -> Optional[TGUserDMChat]:
        with Session(engine) as session:
            # Get active user session
            statement = select(TGUserDMChat).where(
                    TGUserDMChat.user_agent_id == self.user_agent_id,
                    TGUserDMChat.tg_user_id == tg_user_id
                )
            return session.exec(statement).first()


    async def send_direct_message(self, tg_user_id: str, msg: str):
        user_dm_chat = await asyncio.to_thread(self.get_dm_chat_id, tg_user_id)

        if user_dm_chat is None:
            self.logger.error("user dm chat not found")
            return

        await self.application.bot.send_message(user_dm_chat.chat_id, msg)


    def log_interact(self, tg_user_id: str, chat_id: str, input: str, output: str | dict):
        day_folder = datetime.today().strftime('%Y-%m-%d')
        user_folder = Path("persisted_data") / "chats" / day_folder / tg_user_id
        agent_folder = user_folder / f"{self.user_agent_id}"

        agent_folder.mkdir(parents=True, exist_ok=True)

        log_file = agent_folder / f"{chat_id}.txt"

        with open(log_file, "a") as f:
            current_time = datetime.today().strftime('%H:%M:%S')

            formatted_input = input.replace("\n", "<br>")
            f.write(f"[{current_time}] [User] {formatted_input}\n")

            if isinstance(output, dict):
                if "image" in output and output["image"] is not None and output["image"] != "":
                    f.write(f"[{current_time}] [Bot] Image\n")
                elif "text" in output and output["text"] is not None and output["text"] != "":
                    text = output["text"].replace("\n", "<br>")
                    f.write(f"[{current_time}] [Bot] {text}\n")
                else:
                    f.write("My brain is messed up...try me again\n")
            else:
                f.write(f"[{current_time}] [Bot] {output}\n")


    def send_user_notifications(self, loop):

        self.logger.info(f"Notification thread for agent {self.user_agent_id} started!")

        while not self.stopped:
            bot_key = f"TG_BOT_USER_NOTIFICATIONS_{self.user_agent_id}"
            message = cache.lpop(bot_key)

            if message is None:
                time.sleep(1)
            else:
                message_dict = json.loads(message)
                if len(message_dict) != 2:
                    continue

                tg_user_id = message_dict[0]
                msg = message_dict[1]

                try:
                    future = asyncio.run_coroutine_threadsafe(self.send_direct_message(tg_user_id, msg), loop)
                    future.result()
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

        self.logger.info(f"Notification thread for agent {self.user_agent_id} stopped!")


    def start(self) -> None:
        self.logger.info("Starting TG Bot...")

        send_user_notification_thread = Thread(target=self.send_user_notifications, args=(asyncio.get_event_loop(), ))
        send_user_notification_thread.start()

        try:
            self.application.run_polling()
        except Exception as e:
            self.logger.error(e)
            self.logger.error(traceback.format_exc())
        finally:
            self.stopped = True
            send_user_notification_thread.join()

        self.logger.info("TG Bot stopped!")

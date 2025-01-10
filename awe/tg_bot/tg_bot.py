import logging
from telegram import Update, constants
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from awe.awe_agent.awe_agent import AweAgent
from awe.models import UserAgentUserInvocations
from PIL import Image
import io
from pathlib import Path
import asyncio
from collections import deque
from ..models.tg_bot import TGBot as TGBotConfig
from .payment_limit_handler import PaymentLimitHandler
from .staking_handler import StakingHandler
from .help_command import help_command
from .balance_handler import BalanceHandler
from .power_command import power_command
from pathlib import Path
from datetime import datetime

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

        # Payment limit handler
        self.payment_limit_handler = PaymentLimitHandler(self.user_agent_id, self.tg_bot_config, self.aweAgent)

        wallet_command_handler = CommandHandler('wallet', self.payment_limit_handler.wallet_command)
        self.application.add_handler(wallet_command_handler)

        # Chances command
        chances_handler = CommandHandler("chances", self.chances_command)
        self.application.add_handler(chances_handler)

        # Staking handler
        self.staking_handler = StakingHandler(self.user_agent_id, self.tg_bot_config, self.aweAgent)

        # Staking command
        staking_command_handler = CommandHandler("staking", self.staking_handler.staking_command)
        self.application.add_handler(staking_command_handler)

        # Balance handler
        self.balance_handler = BalanceHandler(self.user_agent_id)
        balance_command_handler = CommandHandler("balance", self.balance_handler.balance_command)
        self.application.add_handler(balance_command_handler)

        # Power command
        power_command_handler = CommandHandler("power", power_command)
        self.application.add_handler(power_command_handler)

        # Help command
        help_command_handler = CommandHandler("help", help_command)
        self.application.add_handler(help_command_handler)

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

    async def chances_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.aweAgent.config.awe_token_config.max_invocation_per_payment == 0:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="This Memegent has no invocation limit.")
        else:
            invocation_chances, payment_chances = await self.payment_limit_handler.get_payment_chances(update)

            msg = f"{invocation_chances} messages left for this play."

            if self.aweAgent.config.awe_token_config.max_payment_per_round != 0:
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

    async def check_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE, is_group_chat: bool) -> bool:

        # Check payment limit
        if self.aweAgent.config.awe_token_enabled:
            if not await self.payment_limit_handler.check_deposit(update, context, is_group_chat):
                return False

        return True

    async def increase_invocation(self, tg_user_id: str):
        await asyncio.to_thread(UserAgentUserInvocations.add_invocation, self.user_agent_id, tg_user_id)


    async def respond_dm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not await self.check_limits(update, context, False):
            return

        user_id = str(update.effective_user.id)

        input = "[Private chat] " + update.message.text

        resp = await self.aweAgent.get_response(
            input,
            user_id,
            user_id)

        await self.send_response(resp, update, context)

        await self.increase_invocation(user_id)
        await asyncio.to_thread(self.log_interact, user_id, str(update.effective_chat.id), input, resp)


    async def respond_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        bot_mentioned = False
        entities = update.effective_message.parse_entities(["mention"])
        for k in entities:
            if entities[k] == f"@{self.tg_bot_config.username}":
                bot_mentioned = True

        if update.effective_chat is None:
            await self.send_response({"text": "Chat ID not found"}, update, context)
            return

        chat_id = f"{update.effective_chat.id}"

        if bot_mentioned:
            if not await self.check_limits(update, context, True):
                return

            user_id = str(update.effective_user.id)
            history_messages = await asyncio.to_thread(self.get_group_chat_history, chat_id)

            input = "[Group chat] " + history_messages + "\n" + update.message.text

            resp = await self.aweAgent.get_response(
                input,
                user_id
            )
            await self.send_response(resp, update, context)

            await self.increase_invocation(user_id)
            await asyncio.to_thread(self.log_interact, user_id, chat_id, input, resp)

        else:
            # Record last 5 messages in the channel for agent respond context
            user_text = update.message.text

            user_name = update.message.from_user.first_name
            if update.message.from_user.last_name is not None:
                user_name = user_name + " " + update.message.from_user.last_name

            message = f"{user_name}: {user_text}"

            await asyncio.to_thread(self.update_group_chat_history, message, chat_id)

    async def respond_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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


    def start(self) -> None:
        self.logger.info("Starting TG Bot...")
        self.application.run_polling()

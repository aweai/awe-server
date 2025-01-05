from telegram import Update
from telegram.ext import ContextTypes

async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = "Commands:\n\n\n"

    msg = msg + "/chances - Chances left to interact\n\n"
    msg = msg + "/wallet - Wallet binding\n\n"
    msg = msg + "/staking - Staking info\n\n"

    await context.bot.send_message(update.effective_chat.id, msg)

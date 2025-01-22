from telegram import Update
from telegram.ext import ContextTypes

def get_help_message() -> str:
    msg = "Commands:\n\n\n"

    msg = msg + "/chances - Chances left to interact\n\n"
    msg = msg + "/wallet - Wallet binding\n\n"
    msg = msg + "/staking - Staking info\n\n"
    msg = msg + "/balance - Check your wallet balance\n\n"
    msg = msg + "/power - Power info\n\n"
    msg = msg + "/reset - Clear chat history and start over\n\n"

    return msg

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_help_message()
    await context.bot.send_message(update.effective_chat.id, msg)

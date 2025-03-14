from telegram import Update
from telegram.ext import ContextTypes
from awe.settings import settings

def get_help_message() -> str:
    msg = "Commands:\n\n\n"

    msg = msg + "Commands for this memegent:\n\n"
    msg = msg + "/chances - Chances left to interact\n\n"
    msg = msg + "/reset - Clear chat history and start over\n\n"
    msg = msg + "/staking - Staking info\n\n"

    msg = msg + "Commands for Awe! account:\n\n"
    msg = msg + "/wallet - Wallet binding\n\n"
    msg = msg + "/balance - Check your account balance\n\n"
    msg = msg + "/deposit [amount] - Deposit from wallet into your account\n\n"
    msg = msg + f"/withdraw [amount] - Withdraw to your wallet (A tx fee of $AWE {settings.withdraw_tx_fee} will be charged)\n\n"
    msg = msg + "/power - Power info\n\n"


    return msg

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = get_help_message()
    await context.bot.send_message(update.effective_chat.id, msg)

from telegram import Update
from telegram.ext import ContextTypes
from awe.models.user_referrals import UserAlreadyReferred, CodeNotFound, UserReferrals
import asyncio
import logging
import traceback
from .bot_maintenance import check_maintenance

logger = logging.getLogger("[Power Command]")

async def power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await check_maintenance(update, context):
        return

    if len(context.args) == 0:
        await list_power(update, context)
    elif len(context.args) == 2 and context.args[0] == "add":
        await add_power(update, context)
    else:
        await context.bot.send_message(update.effective_chat.id, get_usage_text())

def get_power_data_message(user_referrals: UserReferrals) -> str:
    msg = f"Multiplier: {user_referrals.get_multiplier()}\n\n"
    msg = msg + f"No. Referrals: {user_referrals.num_activated_referrals}/{user_referrals.num_referrals}\n\n"
    msg = msg + f"Invite friends and let them power you up using:\n/power add {user_referrals.code}\n\n"
    return msg

async def list_power(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user is None:
            update.message.reply_text("User ID not found")
            return None

    user_id = str(update.effective_user.id)

    if user_id is None or user_id == "":
        update.message.reply_text("User ID not found")
        return None

    try:
        user_referrals = await asyncio.to_thread(UserReferrals.get_or_create_user_referrals, user_id)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        await context.bot.send_message(update.effective_chat.id, "Unexpected error. Please try again later.")

    msg = get_power_data_message(user_referrals)
    await context.bot.send_message(update.effective_chat.id, msg)


async def add_power(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user is None:
            update.message.reply_text("User ID not found")
            return None

    user_id = str(update.effective_user.id)

    if user_id is None or user_id == "":
        update.message.reply_text("User ID not found")
        return None

    code = context.args[1]
    try:
        my_user_referrals = await asyncio.to_thread(UserReferrals.add_referred_by, user_id, code)

        msg = "Successfully powered up the user.\n\n"
        msg = msg + get_power_data_message(my_user_referrals)

        await context.bot.send_message(update.effective_chat.id, msg)

    except CodeNotFound:
        await context.bot.send_message(update.effective_chat.id, "Code not found. Please check the code and try again.")
    except UserAlreadyReferred:
        await context.bot.send_message(update.effective_chat.id, "You can only power 1 user.")
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())
        await context.bot.send_message(update.effective_chat.id, "Unexpected error. Please try again later.")


def get_usage_text() -> str:
    usage = "Command usage:\n\n"
    usage = usage + "/power - Check your current power\n"
    usage = usage + "/power add <code> - Add power to user\n"
    return usage

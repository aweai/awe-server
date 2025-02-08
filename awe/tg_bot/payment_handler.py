
from telegram import Update
from telegram.ext import ContextTypes
from awe.models import UserAgentUserInvocations, TgUserAccount, UserAgentData, UserAgent, AweDeveloperAccount, TgUserAgentPayment
from typing import Tuple, Dict
import asyncio
from .base_handler import BaseHandler
import logging
from threading import Lock
from sqlmodel import Session, select
from awe.db import engine
from sqlalchemy.orm import joinedload
from awe.settings import settings
from awe.agent_manager.agent_stats import record_user_payment

logger = logging.getLogger("[PaymentHandler]")

user_locks: Dict[str, Lock] = {}

class PaymentHandler(BaseHandler):

    async def get_chances(self, tg_user_id: str) -> Tuple[int, int]:

        agent_data = await asyncio.to_thread(UserAgentData.get_user_agent_data_by_id, self.user_agent_id)
        user_invocation = await asyncio.to_thread(UserAgentUserInvocations.get_user_invocation, self.user_agent_id, tg_user_id)

        if user_invocation is None or user_invocation.current_round != agent_data.current_round:
            # No payment for current round
            invocation_chances = 0
        elif self.awe_agent.config.awe_token_config.max_invocation_per_payment == 0:
            invocation_chances = -1
        else:
            if user_invocation is None:
                invocation_chances = self.awe_agent.config.awe_token_config.max_invocation_per_payment
            else:
                invocation_chances = self.awe_agent.config.awe_token_config.max_invocation_per_payment - user_invocation.payment_invocations
                if invocation_chances < 0:
                    invocation_chances = 0

        if self.awe_agent.config.awe_token_config.max_payment_per_round == 0:
            payment_chances = -1
        elif user_invocation is None or user_invocation.current_round != agent_data.current_round:
            payment_chances = self.awe_agent.config.awe_token_config.max_payment_per_round
        else:
            payment_chances = self.awe_agent.config.awe_token_config.max_payment_per_round - user_invocation.round_payments
            if payment_chances < 0:
                payment_chances = 0

        return invocation_chances, payment_chances


    async def ask_for_payment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_chat is None:
            return
        user_id = str(update.effective_user.id)

        # Get price
        price = self.awe_agent.config.awe_token_config.user_price

        # Check user balance
        balance, rewards = await asyncio.to_thread(TgUserAccount.get_balance, user_id)

        if balance + rewards < price:
            await context.bot.send_message(
                update.effective_chat.id,
                f"You don't have enough tokens left in your account:\n\nPrice: $AWE {price}.00, Your balance: $AWE {balance + rewards}.00.\n\nPlease deposit using command:\n\n/deposit <amount>"
            )
        else:
            await context.bot.send_message(
                update.effective_chat.id,
                f"You need to pay to use this Memegent:\n\nPrice: $AWE {price}.00, Your balance: $AWE {balance + rewards}.00.\n\nPlease confirm the payment using command:\n\n/pay"
            )


    async def pay_for_current_round(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        if update.effective_user is None or update.effective_chat is None:
            return
        user_id = str(update.effective_user.id)

        try:
            msg = await asyncio.to_thread(self.pay_for_current_round_sync, user_id)
            await context.bot.send_message(update.effective_chat.id, msg)
        except Exception as e:
            logger.error(e)
            await context.bot.send_message(update.effective_chat.id, f"Payment failed. Please try again later")


    def pay_for_current_round_sync(self, user_id: str) -> str:

        logger.info(f"Processing payment from user {user_id} to agent {self.user_agent_id}")

        if user_id not in user_locks:
            user_locks[user_id] = Lock()

        with user_locks[user_id]:
            invocation_chances, payment_chances = asyncio.run(self.get_chances(user_id))
            if invocation_chances != 0:
                return "You have already paid."

            if payment_chances == 0:
                return "You have reached the limit of this round. Please wait for the next round."

            with Session(engine) as session:
                statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == self.user_agent_id)
                user_agent = session.exec(statement).first()

                game_pool_division = user_agent.awe_agent.awe_token_config.game_pool_division
                price = user_agent.awe_agent.awe_token_config.user_price
                pool_share, creator_share, developer_share = settings.tn_share_user_payment(game_pool_division, price)

                # 1. Check and decrease user account balance

                statement = select(TgUserAccount).where(TgUserAccount.tg_user_id == user_id)
                user_account = session.exec(statement).first()

                if user_account is None or user_account.balance + user_account.rewards < price:
                    return f"You don't have enough tokens left in your account ({price}/{user_account.balance + user_account.rewards}).\n\nPlease deposit using command:\n\n/deposit <amount>"

                if user_account.rewards >= price:
                    user_account.rewards = TgUserAccount.rewards - price
                elif user_account.rewards == 0:
                    user_account.balance = TgUserAccount.balance - price
                else:
                    user_account.rewards = TgUserAccount.rewards - user_account.rewards
                    user_account.balance = TgUserAccount.balance - (price - user_account.rewards)

                session.add(user_account)

                # 2. Add agent pool

                if pool_share != 0:
                    user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote + pool_share

                # 3. Add creator account balance

                if creator_share != 0:
                    user_agent.agent_data.awe_token_creator_balance = UserAgentData.awe_token_creator_balance + creator_share
                    user_agent.agent_data.total_income_shares = UserAgentData.total_income_shares + creator_share

                session.add(user_agent.agent_data)

                # 4. Add developer account balance

                statement = select(AweDeveloperAccount)
                developer_account = session.exec(statement).first()

                if developer_account is None:
                    developer_account = AweDeveloperAccount(
                        balance=developer_share
                    )
                else:
                    developer_account.balance = AweDeveloperAccount.balance + developer_share

                session.add(developer_account)

                # 5. Reset user payment invocation count

                statement = select(UserAgentUserInvocations).where(
                    UserAgentUserInvocations.user_agent_id == self.user_agent_id,
                    UserAgentUserInvocations.tg_user_id == user_id
                )

                user_invoke = session.exec(statement).first()
                if user_invoke is None:
                    user_invoke = UserAgentUserInvocations(
                        user_agent_id=self.user_agent_id,
                        tg_user_id=user_id,
                        current_round=user_agent.agent_data.current_round
                    )
                else:
                    user_invoke.payment_invocations = 0

                    if user_invoke.current_round != user_agent.agent_data.current_round:
                        user_invoke.current_round = user_agent.agent_data.current_round
                        user_invoke.round_payments = 1
                    else:
                        user_invoke.round_payments = UserAgentUserInvocations.round_payments + 1

                session.add(user_invoke)

                # 6. Update stats

                record_user_payment(self.user_agent_id, pool_share, creator_share, session)

                # 7. Record user agent payment

                user_agent_payment = TgUserAgentPayment(
                    user_agent_id=self.user_agent_id,
                    tg_user_id=user_id,
                    round=user_agent.agent_data.current_round,
                    amount=price
                )
                session.add(user_agent_payment)

                session.commit()

        logger.info(f"Payment done from user {user_id} to agent {self.user_agent_id}")

        return "The payment is received. Have fun!"

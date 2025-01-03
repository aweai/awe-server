from awe.models import TgUserDeposit, TgUserWithdraw, UserAgentData, UserStaking, TGBotUserWallet, UserAgent, UserAgentUserInvocations
from awe.blockchain import awe_on_chain
from time import sleep
from awe.settings import settings
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from awe.db import engine
import logging
import traceback
from threading import Lock
from typing import Dict
from awe.models.utils import unix_timestamp_in_seconds
from .agent_stats import record_user_withdraw, record_user_payment

logger = logging.getLogger("[Agent Fund]")

agent_locks: Dict[int, Lock] = {}
staking_locks: Dict[int, Lock] = {}

class TransferToUserNotAllowedException(Exception):
    pass

class ReleaseStakingNotAllowedException(Exception):
    pass

def collect_user_fund(
    action: str,
    amount: int,
    agent_id: int,
    tg_user_id: str,
    approve_tx: str,
):
    # Wait for the finalize of the approve tx before executing
    sleep(20)

    try:
        # Wait for the approve tx to be confirmed before next step
        awe_on_chain.wait_for_tx_confirmation(approve_tx, 30)

        if action == "user_payment":
            collect_user_payment(agent_id, tg_user_id)

        elif action == "user_staking":
            collect_user_staking(agent_id, tg_user_id, amount)

    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def collect_user_payment(agent_id: int, tg_user_id: str):

    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()

        # We will use the agent price as the amount here
        amount = user_agent.awe_agent.awe_token_config.user_price

        # Collect user payment
        tx = awe_on_chain.collect_user_payment(user_wallet.address, user_agent.user_address, amount)

        pool_share, _, _ = settings.tn_share_user_payment(amount)

        # Add agent pool
        user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote + pool_share

        session.add(user_agent.agent_data)
        session.commit()

        session.refresh(user_agent)

        # Reset user payment invocation count
        if user_agent.awe_agent.awe_token_config.max_invocation_per_payment != 0:
            UserAgentUserInvocations.user_paid(agent_id, tg_user_id)

        user_address = user_wallet.address

    # Record stats
    record_user_payment(agent_id, user_address, amount)

    # Record the transfer tx
    with Session(engine) as session:

        user_deposit = TgUserDeposit(
            user_agent_id=agent_id,
            tg_user_id=tg_user_id,
            user_agent_round=user_agent.agent_data.current_round,
            address=user_wallet.address,
            amount=amount,
            tx_hash=tx
        )

        session.add(user_deposit)
        session.commit()


def collect_user_staking(agent_id: int, tg_user_id: str, amount: int):

    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        # Collect user staking
        tx = awe_on_chain.collect_user_staking(user_wallet.address, amount)

        # Record the transfer tx
        user_staking = UserStaking(
            tg_user_id=tg_user_id,
            user_agent_id=agent_id,
            amount=amount,
            tx_hash=tx
        )

        session.add(user_staking)

        # Add agent staking pool
        statement = select(UserAgentData).where(UserAgentData.user_agent_id == agent_id)
        user_agent_data = session.exec(statement).first()
        user_agent_data.awe_token_staking = UserAgentData.awe_token_staking + amount

        session.add(user_agent_data)

        session.commit()

        # TODO: Staking In Stats


def transfer_to_user(agent_id: int, tg_user_id: str, user_address: str, amount: int) -> str:

    try:
        amount = int(amount)
    except:
        raise TransferToUserNotAllowedException("Invalid amount provided!")

    logger.info(f"Transferring {amount} tokens")

    # Lock the agent to prevent race condition
    if agent_id not in agent_locks:
        agent_locks[agent_id] = Lock()

    with agent_locks[agent_id]:
        with Session(engine) as session:
            statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
            user_agent = session.exec(statement).first()

            current_round = user_agent.agent_data.current_round

            if amount > user_agent.awe_agent.awe_token_config.max_token_per_tx:
                raise TransferToUserNotAllowedException("Token amount exceeds the maximum allowed!")

            if amount + user_agent.agent_data.awe_token_round_transferred > user_agent.awe_agent.awe_token_config.max_token_per_round or user_agent.agent_data.awe_token_quote < amount:
                raise TransferToUserNotAllowedException("Token amount exceeds the maximum allowed!")

            # Update the data in db first

            # Update round data
            user_agent.agent_data.awe_token_round_transferred = UserAgentData.awe_token_round_transferred + amount

            # Update game pool
            user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote - amount

            session.add(user_agent.agent_data)
            session.commit()

    # Send the transaction
    tx = awe_on_chain.transfer_to_user(user_address, amount)

    # Record stats
    record_user_withdraw(agent_id, user_address, amount)

    # Record the tx
    with Session(engine) as session:
        user_withdraw = TgUserWithdraw(
            user_agent_id=agent_id,
            tg_user_id=tg_user_id,
            user_agent_round=current_round,
            address=user_address,
            amount=amount,
            tx_hash=tx
        )

        session.add(user_withdraw)

    return tx


def release_user_staking(agent_id: int, tg_user_id: str, staking_id: int, wallet_address: str) -> str:

    # Lock the agent to prevent race condition
    if staking_id not in staking_locks:
        staking_locks[staking_id] = Lock()

    with staking_locks[staking_id]:

        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.id == staking_id,
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == agent_id,
                UserStaking.released_at.is_(None)
            )

            user_staking = session.exec(statement).first()

            if user_staking is None:
                raise ReleaseStakingNotAllowedException("Staking not found")

            now = unix_timestamp_in_seconds()
            if now - user_staking.created_at < settings.tn_user_staking_locking_days * 86400:
                raise ReleaseStakingNotAllowedException("Staking is still locked!")

            amount = user_staking.amount

            logger.info(f"[{staking_id}] Releasing user staking: {amount}")

            # Update the db first
            user_staking.released_at = now
            session.add(user_staking)
            session.commit()

    # Send the transaction
    logger.info(f"[{staking_id}] Sending staking tokens to user: {wallet_address}:{amount}")
    tx = awe_on_chain.transfer_to_user(wallet_address, amount)

    logger.info(f"[{staking_id}] Release staking tx sent: {tx}")

    # Record the tx
    with Session(engine) as session:
        statement = select(UserStaking).where(
            UserStaking.id == staking_id,
            UserStaking.tg_user_id == tg_user_id,
            UserStaking.user_agent_id == agent_id
        )

        user_staking = session.exec(statement).first()

        user_staking.release_tx_hash = tx
        session.add(user_staking)
        session.commit()

    return tx

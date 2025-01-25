from awe.models import TgUserDeposit, \
                        TgUserWithdraw, UserAgentData, UserStaking, \
                        TGBotUserWallet, UserAgent, UserAgentUserInvocations, \
                        UserReferrals
from awe.blockchain import awe_on_chain
from awe.settings import settings
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from awe.db import engine
import logging
import traceback
from threading import Lock
from typing import Dict, List
from awe.models.utils import unix_timestamp_in_seconds
from .agent_stats import record_user_withdraw, record_user_payment, record_user_staking, record_user_staking_release
from awe.tg_bot.user_notification import send_user_notification

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
    send_user_notification(agent_id, tg_user_id, f"We are processing the transaction in the background. Please wait...")

    try:
        if action == "user_payment":
            collect_user_payment(agent_id, tg_user_id, approve_tx)

        elif action == "user_staking":
            collect_user_staking(agent_id, tg_user_id, amount, approve_tx)

    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def collect_user_payment(agent_id: int, tg_user_id: str, approve_tx: str):

    # Record the request
    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()

        # We will use the agent price as the amount here
        amount = user_agent.awe_agent.awe_token_config.user_price
        user_wallet_address = user_wallet.address
        agent_creator_wallet = user_agent.user_address
        game_pool_division = user_agent.awe_agent.awe_token_config.game_pool_division

        pool_share, creator_share, _ = settings.tn_share_user_payment(game_pool_division, amount)

        user_deposit = TgUserDeposit(
            user_agent_id=agent_id,
            tg_user_id=tg_user_id,
            user_agent_round=user_agent.agent_data.current_round,
            address=user_wallet.address,
            amount=amount,
            approve_tx_hash=approve_tx
        )

        session.add(user_deposit)
        session.commit()
        session.refresh(user_deposit)
        user_deposit_id = user_deposit.id

    # Wait for the approve tx to be confirmed before next step
    awe_on_chain.wait_for_tx_confirmation(approve_tx, 30)

    # Collect user payment
    tx = awe_on_chain.collect_user_payment(user_deposit_id, user_wallet_address, agent_creator_wallet, amount, game_pool_division)

    # Record stats
    # Must before tx_hash is updated in TgUserDeposit
    record_user_payment(agent_id, user_wallet_address, pool_share, creator_share)

     # Record the transfer tx
    with Session(engine) as session:

        statement = select(TgUserDeposit).where(
            TgUserDeposit.id == user_deposit_id
        )

        user_deposit = session.exec(statement).first()
        user_deposit.tx_hash = tx
        session.add(user_deposit)
        session.commit()

    with Session(engine) as session:

        statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()

        if pool_share != 0:
            # Add agent pool
            user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote + pool_share

            session.add(user_agent.agent_data)
            session.commit()
            session.refresh(user_agent)

    # Reset user payment invocation count
    UserAgentUserInvocations.user_paid(agent_id, tg_user_id)

    # Activate user referral
    UserReferrals.activate(tg_user_id)

    send_user_notification(agent_id, tg_user_id, "The payment is received. Have fun!")


def collect_user_staking(agent_id: int, tg_user_id: str, amount: int, approve_tx: str):

    # Record the request
    with Session(engine) as session:

        # Record the transfer tx
        user_staking = UserStaking(
            tg_user_id=tg_user_id,
            user_agent_id=agent_id,
            amount=amount,
            approve_tx_hash=approve_tx
        )

        session.add(user_staking)
        session.commit()
        session.refresh(user_staking)
        staking_id = user_staking.id


    # Wait for the approve tx to be confirmed before next step
    awe_on_chain.wait_for_tx_confirmation(approve_tx, 30)

    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()
        wallet_address = user_wallet.address

        # Collect user staking
        tx = awe_on_chain.collect_user_staking(user_wallet.address, amount)

        # Update the staking record

        statement = select(UserStaking).where(
            UserStaking.id == staking_id
        )
        user_staking = session.exec(statement).first()
        user_staking.tx_hash = tx
        session.add(user_staking)
        session.commit()

    record_user_staking(agent_id, wallet_address, amount)

    send_user_notification(agent_id, tg_user_id, "The staking is in position. Have fun!")


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

            # Record the transfer
            user_withdraw = TgUserWithdraw(
                user_agent_id=agent_id,
                tg_user_id=tg_user_id,
                user_agent_round=current_round,
                address=user_address,
                amount=amount
            )

            session.add(user_withdraw)
            session.commit()
            session.refresh(user_withdraw)

    # Send the transaction
    tx = awe_on_chain.transfer_to_user(user_address, amount)

    # Record the tx
    with Session(engine) as session:
        user_withdraw.tx_hash = tx
        session.add(user_withdraw)
        session.commit()

    # Record stats
    record_user_withdraw(agent_id, user_address, amount)

    return tx


def batch_transfer_to_users(agent_id: int, user_ids: List[str], user_addresses: List[str], amounts: List[int]) -> str:

    if len(user_ids) > 20:
        raise Exception("number of users exceeds the maximum allowed in a single transaction")

    # Lock the agent to prevent race condition
    if agent_id not in agent_locks:
        agent_locks[agent_id] = Lock()

    max_amount = max(amounts)
    total_amount = sum(amounts)

    with agent_locks[agent_id]:
        with Session(engine) as session:
            statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
            user_agent = session.exec(statement).first()

            current_round = user_agent.agent_data.current_round

            if max_amount > user_agent.awe_agent.awe_token_config.max_token_per_tx:
                raise TransferToUserNotAllowedException("Token amount exceeds the maximum allowed!")

            if total_amount + user_agent.agent_data.awe_token_round_transferred > user_agent.awe_agent.awe_token_config.max_token_per_round or user_agent.agent_data.awe_token_quote < total_amount:
                raise TransferToUserNotAllowedException("Token amount exceeds the maximum allowed!")

            # Update the data in db first

            # Update round data
            user_agent.agent_data.awe_token_round_transferred = UserAgentData.awe_token_round_transferred + total_amount

            # Update game pool
            user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote - total_amount

            session.add(user_agent.agent_data)

            # Record the withdraws
            user_withdraws: List[TgUserWithdraw] = []

            for idx, user_id in enumerate(user_ids):
                user_withdraw = TgUserWithdraw(
                    user_agent_id=agent_id,
                    tg_user_id=user_id,
                    user_agent_round=current_round,
                    address=user_addresses[idx],
                    amount=amounts[idx]
                )

                session.add(user_withdraw)
                user_withdraws.append(user_withdraw)

            session.commit()

            for user_withdraw in user_withdraws:
                session.refresh(user_withdraw)

    # Send the transaction
    tx = awe_on_chain.batch_transfer_to_users(user_addresses, amounts)

    # Record the transaction
    with Session(engine) as session:
        for user_withdraw in user_withdraws:
            user_withdraw.tx_hash = tx
            session.add(user_withdraw)

        session.commit()

    # Record stats
    for user_withdraw in user_withdraws:
        record_user_withdraw(agent_id, user_withdraw.address, user_withdraw.amount)

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

            if user_staking.tx_hash is None or user_staking.tx_hash == "":
                raise ReleaseStakingNotAllowedException("Staking not confirmed")

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

    record_user_staking_release(agent_id, wallet_address, amount)

    return tx

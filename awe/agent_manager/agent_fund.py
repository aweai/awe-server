from awe.models import TgUserDeposit, \
                        TgUserWithdraw, UserAgentData, UserStaking, \
                        TGBotUserWallet, UserAgent, TgUserAccount, UserReferrals, AweDeveloperAccount
from awe.models.tg_user_deposit import TgUserDepositStatus
from awe.models.user_staking import UserStakingStatus
from awe.models.tg_user_withdraw import TgUserWithdrawStatus
from awe.models.game_pool_charge import GamePoolCharge, GamePoolChargeStatus
from awe.models.user_agent_refund import UserAgentRefund, UserAgentRefundStatus
from awe.models.agent_account_withdraw import AgentAccountWithdraw, AgentAccountWithdrawStatus
from awe.models.user_agent_staking import UserAgentStaking, UserAgentStakingStatus
from awe.blockchain import awe_on_chain
from awe.settings import settings
from sqlalchemy.orm import joinedload
from sqlmodel import Session, select
from awe.db import engine
import logging
import traceback
from threading import Lock
from typing import Dict
from awe.models.utils import unix_timestamp_in_seconds
from .agent_stats import record_user_staking, record_user_staking_release
from awe.tg_bot.user_notification import send_user_notification

logger = logging.getLogger("[Agent Fund]")

staking_locks: Dict[int, Lock] = {}
withdraw_locks: Dict[int, Lock] = {}
creator_withdraw_locks: Dict[int, Lock] = {}

class WithdrawNotAllowedException(Exception):
    pass

class ReleaseStakingNotAllowedException(Exception):
    pass


def collect_agent_creation_staking(
    creator_address: str,
    approve_tx: str
):
    logger.info(f"[Collect Agent Creation] Creating agent for wallet: {creator_address}")

    # Record the request
    with Session(engine) as session:
        agent_creation_staking = UserAgentStaking(
            address=creator_address,
            amount=settings.tn_agent_staking_amount,
            approve_tx_hash=approve_tx
        )
        session.add(agent_creation_staking)
        session.commit()
        session.refresh(agent_creation_staking)
        agent_creation_staking_id = agent_creation_staking.id

    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Request recorded!")

    try:
        # Wait for the approve tx to be confirmed before next step
        awe_on_chain.wait_for_tx_confirmation(approve_tx, settings.solana_tx_wait_timeout)
    except Exception as e:
        logger.error(e)
        logger.error(f"[Collect Agent Creation] [{agent_creation_staking_id}] Error waiting for approve tx confirmation")
        UserAgentStaking.update_status(agent_creation_staking_id, UserAgentStakingStatus.FAILED)
        return

    UserAgentStaking.update_status(agent_creation_staking_id, UserAgentStakingStatus.APPROVED)
    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Approve tx confirmed!")

    # Collect user deposit
    tx, last_valid_block_height = awe_on_chain.collect_agent_creation_staking(agent_creation_staking_id, creator_address, settings.tn_agent_staking_amount)

    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Transfer tx sent! {tx}")

    # Record the transfer tx
    with Session(engine) as session:

        statement = select(UserAgentStaking).where(
            UserAgentStaking.id == agent_creation_staking_id
        )

        agent_creation_staking = session.exec(statement).first()
        agent_creation_staking.tx_hash = tx
        agent_creation_staking.tx_last_valid_block_height = last_valid_block_height
        agent_creation_staking.status = UserAgentStakingStatus.TX_SENT
        session.add(agent_creation_staking)
        session.commit()

    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Transfer tx recorded!")


def finalize_agent_creation_staking(agent_creation_staking_id: int):
    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Finalizing agent creation")

    with Session(engine) as session:
        statement = select(UserAgentStaking).where(
            UserAgentStaking.id == agent_creation_staking_id
        )
        agent_creation_staking = session.exec(statement).first()

        # 1. Update the agent creation staking status

        agent_creation_staking.status = UserAgentStakingStatus.SUCCESS
        session.add(agent_creation_staking)

        # 2. Create the agent

        user_agent = UserAgent(
            user_address=agent_creation_staking.address,
            staking_amount=agent_creation_staking.amount,
            agent_data=UserAgentData()
        )
        session.add(user_agent)

        session.commit()

    logger.info(f"[Collect Agent Creation] [{agent_creation_staking_id}] Agent creation finalized!")


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
            collect_user_deposit(agent_id, tg_user_id, amount, approve_tx)

        elif action == "user_staking":
            collect_user_staking(agent_id, tg_user_id, amount, approve_tx)

    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def collect_user_deposit(agent_id: int, tg_user_id: str, amount: int, approve_tx: str):

    # Record the request
    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()

        statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
        user_agent = session.exec(statement).first()

        user_wallet_address = user_wallet.address

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

    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] User Deposit created! {approve_tx}")

    try:
        # Wait for the approve tx to be confirmed before next step
        awe_on_chain.wait_for_tx_confirmation(approve_tx, settings.solana_tx_wait_timeout)
    except Exception as e:
        logger.error(e)
        logger.error(f"[Collect User Deposit] [User Deposit {user_deposit_id}] Error waiting for approve tx confirmation")
        TgUserDeposit.update_status(user_deposit_id, TgUserDepositStatus.FAILED)
        send_user_notification(agent_id, tg_user_id, f"Payment error: we cannot confirm the approve tx. You can safely try to pay again now.")
        return

    TgUserDeposit.update_status(user_deposit_id, TgUserDepositStatus.APPROVED)
    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] Approve tx confirmed!")

    # Collect user deposit
    tx, last_valid_block_height = awe_on_chain.collect_user_deposit(user_deposit_id, user_wallet_address, amount)

    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] Transfer tx sent! {tx}")

    # Record the transfer tx
    with Session(engine) as session:

        statement = select(TgUserDeposit).where(
            TgUserDeposit.id == user_deposit_id
        )

        user_deposit = session.exec(statement).first()
        user_deposit.tx_hash = tx
        user_deposit.tx_last_valid_block_height = last_valid_block_height
        user_deposit.status = TgUserDepositStatus.TX_SENT
        session.add(user_deposit)
        session.commit()

    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] Transfer tx recorded!")


def finalize_user_deposit(user_deposit_id: int):
    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] Finalizing user deposit")
    with Session(engine) as session:

        statement = select(TgUserDeposit).where(
            TgUserDeposit.id == user_deposit_id
        )
        user_deposit = session.exec(statement).first()
        user_agent_id = user_deposit.user_agent_id
        tg_user_id = user_deposit.tg_user_id

        # 1. Add balance to tg user account

        statement = select(TgUserAccount).where(TgUserAccount.tg_user_id == user_deposit.tg_user_id)
        tg_user_account = session.exec(statement).first()

        if tg_user_account is None:
            tg_user_account = TgUserAccount(
                tg_user_id=user_deposit.tg_user_id,
                balance=user_deposit.amount
            )
        else:
            tg_user_account.balance = TgUserAccount.balance + user_deposit.amount

        session.add(tg_user_account)

        # 2. Activate user referral

        UserReferrals.activate(tg_user_id, session)

        # 3. Update user deposit status

        user_deposit.status = TgUserDepositStatus.SUCCESS
        session.add(user_deposit)

        session.commit()

    send_user_notification(user_agent_id, tg_user_id, "The deposit is received. Have fun!")
    logger.info(f"[Collect User Deposit] [User Deposit {user_deposit_id}] User deposit finalized!")


def collect_user_staking(agent_id: int, tg_user_id: str, amount: int, approve_tx: str):

    # Record the request
    with Session(engine) as session:

        # Get user wallet info from db
        statement = select(TGBotUserWallet).where(TGBotUserWallet.user_agent_id == agent_id, TGBotUserWallet.tg_user_id == tg_user_id)
        user_wallet = session.exec(statement).first()
        wallet_address = user_wallet.address

        # Record the transfer tx
        user_staking = UserStaking(
            tg_user_id=tg_user_id,
            user_agent_id=agent_id,
            address=wallet_address,
            amount=amount,
            approve_tx_hash=approve_tx
        )

        session.add(user_staking)
        session.commit()
        session.refresh(user_staking)
        staking_id = user_staking.id

    logger.info(f"[Collect User Staking] [User Staking {staking_id}] User Staking created! {approve_tx}")

    try:
        # Wait for the approve tx to be confirmed before next step
        awe_on_chain.wait_for_tx_confirmation(approve_tx, settings.solana_tx_wait_timeout)
    except Exception as e:
        logger.error(e)
        logger.error(f"[Collect User Staking] [User Staking {staking_id}] Error waiting for approve tx confirmation")
        UserStaking.update_staking_status(staking_id, UserStakingStatus.FAILED)
        send_user_notification(agent_id, tg_user_id, f"Staking error: we cannot confirm the approve tx. You can safely try to stake again now.")
        return

    logger.info(f"[Collect User Staking] [User Staking {staking_id}] Approve tx confirmed!")

    # Collect user staking
    tx, last_valid_block_height = awe_on_chain.collect_user_staking(staking_id, wallet_address, amount)

    logger.info(f"[Collect User Staking] [User Staking {staking_id}] Transfer tx sent! {tx}")

    # Update the staking record
    with Session(engine) as session:
        statement = select(UserStaking).where(
            UserStaking.id == staking_id
        )
        user_staking = session.exec(statement).first()
        user_staking.tx_hash = tx
        user_staking.tx_last_valid_block_height = last_valid_block_height
        user_staking.status = UserStakingStatus.TX_SENT
        session.add(user_staking)
        session.commit()

    logger.info(f"[Collect User Staking] [User Staking {staking_id}] Transfer tx recorded!")


def finalize_user_staking(staking_id: int):
    with Session(engine) as session:
        statement = select(UserStaking).where(
            UserStaking.id == staking_id
        )
        user_staking = session.exec(statement).first()

        agent_id = user_staking.user_agent_id
        tg_user_id = user_staking.tg_user_id

        record_user_staking(user_staking.user_agent_id, user_staking.address, user_staking.amount, session)

        user_staking.status = UserStakingStatus.SUCCESS
        session.add(user_staking)

        session.commit()

    logger.info(f"[Collect User Staking] [User Staking {staking_id}] Staking finalized!")

    send_user_notification(agent_id, tg_user_id, "The staking is in position. Have fun!")


def withdraw_to_user(user_agent_id: int, tg_user_id: str, user_address: str, amount: int) -> str:

    logger.info(f"[Withdraw To User] Withdraw $AWE {amount} to user {tg_user_id}({user_address})")

    # Lock the user to prevent race condition
    if tg_user_id not in withdraw_locks:
        withdraw_locks[tg_user_id] = Lock()

    with withdraw_locks[tg_user_id]:
        with Session(engine) as session:
            # Update the data in db first
            statement = select(TgUserAccount).where(TgUserAccount.tg_user_id == tg_user_id)
            tg_user_account = session.exec(statement).first()

            if tg_user_account.balance < amount + settings.withdraw_tx_fee:
                raise WithdrawNotAllowedException(f"Not enough tokens to withdraw in your account: {amount + settings.withdraw_tx_fee}/{tg_user_account.balance}")

            tg_user_account.balance = TgUserAccount.balance - (amount + settings.withdraw_tx_fee)

            session.add(tg_user_account)

            # 2. Increase the developer account balance (collect the tx fee)
            statement = select(AweDeveloperAccount)
            developer_account = session.exec(statement).first()

            if developer_account is None:
                developer_account = AweDeveloperAccount(
                    balance=settings.withdraw_tx_fee
                )
            else:
                developer_account.balance = AweDeveloperAccount.balance + settings.withdraw_tx_fee

            session.add(developer_account)

            # Record the withdraw
            user_withdraw = TgUserWithdraw(
                user_agent_id=user_agent_id,
                tg_user_id=tg_user_id,
                address=user_address,
                amount=amount
            )

            session.add(user_withdraw)
            session.commit()
            session.refresh(user_withdraw)
            user_withdraw_id = user_withdraw.id

    logger.info(f"[Withdraw To User] [User Withdraw {user_withdraw_id}] Withdraw created!")

    # Send the transaction
    tx, last_valid_block_height = awe_on_chain.transfer_to_user(f"withdraw_{user_withdraw_id}", user_address, amount)

    logger.info(f"[Withdraw To User] [User Withdraw {user_withdraw_id}] Tx sent! {tx}")

    # Record the tx
    with Session(engine) as session:
        statement = select(TgUserWithdraw).where(TgUserWithdraw.id == user_withdraw_id)
        user_withdraw = session.exec(statement).first()

        user_withdraw.tx_hash = tx
        user_withdraw.tx_last_valid_block_height = last_valid_block_height
        user_withdraw.status = TgUserWithdrawStatus.TX_SENT

        session.add(user_withdraw)
        session.commit()

    logger.info(f"[Withdraw To User] [User Withdraw {user_withdraw_id}] Tx recorded!")

    return tx


def finalize_withdraw_to_user(user_withdraw_id: int):

    logger.info(f"[Withdraw To User] [User Withdraw {user_withdraw_id}] Finalizing user withdraw")

    with Session(engine) as session:
        statement = select(TgUserWithdraw).where(TgUserWithdraw.id == user_withdraw_id)
        user_withdraw = session.exec(statement).first()
        user_withdraw.status = TgUserWithdrawStatus.SUCCESS
        session.add(user_withdraw)

        session.commit()

    logger.info(f"[Withdraw To User] [User Withdraw {user_withdraw_id}] User withdraw finalized!")


def release_user_staking(agent_id: int, tg_user_id: str, staking_id: int, wallet_address: str) -> str:

    # Lock the agent to prevent race condition
    if staking_id not in staking_locks:
        staking_locks[staking_id] = Lock()

    with staking_locks[staking_id]:

        logger.info(f"[Release User Staking] [{staking_id}] Releasing user staking")

        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.id == staking_id,
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == agent_id,
                UserStaking.release_status.is_(None)
            )

            user_staking = session.exec(statement).first()

            if user_staking is None:
                raise ReleaseStakingNotAllowedException("Staking not found")

            if user_staking.status != UserStakingStatus.SUCCESS:
                raise ReleaseStakingNotAllowedException("Staking not success")

            now = unix_timestamp_in_seconds()
            if now - user_staking.created_at < settings.tn_user_staking_locking_days * 86400:
                raise ReleaseStakingNotAllowedException("Staking is still locked!")

            amount = user_staking.amount

            logger.info(f"[{staking_id}] Releasing user staking: {amount}")

            user_staking_id = user_staking.id

            # Update the db first
            user_staking.release_status = UserStakingStatus.APPROVING
            session.add(user_staking)
            session.commit()

    # Send the transaction
    logger.info(f"[Release User Staking] [{staking_id}] Sending tx: {wallet_address}:{amount}")
    tx, last_valid_block_height = awe_on_chain.transfer_to_user(f"release_staking_{user_staking_id}", wallet_address, amount)

    logger.info(f"[Release User Staking] [{staking_id}] Release staking tx sent: {tx}")

    # Record the tx
    with Session(engine) as session:
        statement = select(UserStaking).where(UserStaking.id == staking_id)
        user_staking = session.exec(statement).first()

        user_staking.release_tx_hash = tx
        user_staking.tx_last_valid_block_height = last_valid_block_height # reuse the same field
        user_staking.release_status = UserStakingStatus.TX_SENT
        session.add(user_staking)
        session.commit()

    logger.info(f"[Release User Staking] [{staking_id}] Release staking tx recorded!")

    return tx


def finalize_release_staking(staking_id: int):

    logger.info(f"[Release User Staking] [{staking_id}] Finalizing")

    with Session(engine) as session:
        statement = select(UserStaking).where(UserStaking.id == staking_id)
        user_staking = session.exec(statement).first()

        record_user_staking_release(user_staking.user_agent_id, user_staking.address, user_staking.amount, session)

        user_staking.release_status = UserStakingStatus.SUCCESS
        user_staking.released_at = unix_timestamp_in_seconds()
        session.add(user_staking)

        session.commit()

    logger.info(f"[Release User Staking] [{staking_id}] Finalized!")


def collect_game_pool_charge(agent_id: int, user_address: str, amount: int, approve_tx: str):

    # Record the charge request

    with Session(engine) as session:
        game_pool_charge = GamePoolCharge(
            user_agent_id=agent_id,
            address=user_address,
            amount=amount,
            approve_tx_hash=approve_tx
        )
        session.add(game_pool_charge)
        session.commit()
        session.refresh(game_pool_charge)

        charge_id = game_pool_charge.id

    logger.info(f"[Game Pool Charge] [{charge_id}] Game pool charge request recorded! {approve_tx}")

    try:
        awe_on_chain.wait_for_tx_confirmation(approve_tx, settings.solana_tx_wait_timeout)
    except Exception as e:
        logger.error(e)
        GamePoolCharge.update_status(charge_id, GamePoolChargeStatus.FAILED)
        raise Exception(f"[Game Pool Charge] [{charge_id}] Cannot confirm the apporve tx.")

    logger.info(f"[Game Pool Charge] [{charge_id}] Approve tx confirmed!")

    collect_tx, last_valid_block_height = awe_on_chain.collect_game_pool_charge(charge_id, user_address, amount)

    logger.info(f"[Game Pool Charge] [{charge_id}] Transfer tx sent! {collect_tx}")

    with Session(engine) as session:
        statement = select(GamePoolCharge).where(GamePoolCharge.id == charge_id)
        game_pool_charge = session.exec(statement).first()
        game_pool_charge.tx_hash = collect_tx
        game_pool_charge.tx_last_valid_block_height = last_valid_block_height
        game_pool_charge.status = GamePoolChargeStatus.TX_SENT
        session.add(game_pool_charge)
        session.commit()

    logger.info(f"[Game Pool Charge] [{charge_id}] Transfer tx recorded!")


def finalize_game_pool_charge(charge_id: int):

    with Session(engine) as session:

        statement = select(GamePoolCharge).where(GamePoolCharge.id == charge_id)
        game_pool_charge = session.exec(statement).first()

        statement = select(UserAgent).where(UserAgent.id == game_pool_charge.user_agent_id)
        user_agent = session.exec(statement).first()

        # Update the game pool
        user_agent.agent_data.awe_token_quote = UserAgentData.awe_token_quote + game_pool_charge.amount
        session.add(user_agent.agent_data)

        # Update the charge status
        game_pool_charge.status = GamePoolChargeStatus.SUCCESS
        session.add(game_pool_charge)

        session.commit()

    logger.info(f"[Game Pool Charge] [{charge_id}] Game pool charge finalized!")


def refund_agent_staking(agent_id: int, creator_address: str, amount: int):

    logger.info(f"Returning staking for agent {agent_id}({creator_address}): {amount}")

    # Record the refund request

    with Session(engine) as session:
        agent_refund = UserAgentRefund(
            user_agent_id=agent_id,
            address=creator_address,
            amount=amount
        )

        session.add(agent_refund)
        session.commit()
        session.refresh(agent_refund)

        refund_id = agent_refund.id

    logger.info(f"[Refund Agent Staking] [{refund_id}] request created!")

    tx, last_valid_block_height = awe_on_chain.transfer_to_user(f"agent_refund_{refund_id}", creator_address, amount)

    logger.info(f"[Refund Agent Staking] [{refund_id}] tx sent! {tx}")

    # Update the refund request

    with Session(engine) as session:
        statement = select(UserAgentRefund).where(UserAgentRefund.id == refund_id)
        agent_refund = session.exec(statement).first()

        agent_refund.tx_hash = tx
        agent_refund.tx_last_valid_block_height = last_valid_block_height
        agent_refund.status = UserAgentRefundStatus.TX_SENT

        session.add(agent_refund)
        session.commit()

    logger.info(f"[Refund Agent Staking] [{refund_id}] tx recorded!")


def finalize_refund_agent_staking(refund_id: int):

    logger.info(f"[Refund Agent Staking] [{refund_id}] finalizing agent refund")

    with Session(engine) as session:
        statement = select(UserAgentRefund).where(UserAgentRefund.id == refund_id)
        agent_refund = session.exec(statement).first()

        agent_refund.status = UserAgentRefundStatus.SUCCESS

        session.add(agent_refund)
        session.commit()

    logger.info(f"[Refund Agent Staking] [{refund_id}] refund finalized!")


def withdraw_to_creator(agent_id: int, amount: int):

    # Record the withdraw request
    logger.info(f"[Withdraw To Creator] Withdraw $AWE {amount} to the creator of agent {agent_id}")

    # Lock the user to prevent race condition
    if agent_id not in creator_withdraw_locks:
        creator_withdraw_locks[agent_id] = Lock()

    with creator_withdraw_locks[agent_id]:

        logger.info(f"[Withdraw To Creator] Processing withdraw $AWE {amount} to the creator of agent {agent_id}")

        with Session(engine) as session:

            statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(UserAgent.id == agent_id)
            user_agent = session.exec(statement).first()

            agent_creator_address = user_agent.user_address

            if amount + settings.withdraw_tx_fee > user_agent.agent_data.awe_token_creator_balance:
                logger.info(f"[Withdraw To Creator] Not enough tokens to withdraw in the agent account: {amount + settings.withdraw_tx_fee}/{user_agent.agent_data.awe_token_creator_balance}")
                raise WithdrawNotAllowedException(f"Not enough tokens to withdraw in the agent account: {amount + settings.withdraw_tx_fee}/{user_agent.agent_data.awe_token_creator_balance}")

            # 1. Decrease the agent account balance
            user_agent.agent_data.awe_token_creator_balance = UserAgentData.awe_token_creator_balance - (amount + settings.withdraw_tx_fee)
            session.add(user_agent.agent_data)


            # 2. Increase the developer account balance (collect the tx fee)
            statement = select(AweDeveloperAccount)
            developer_account = session.exec(statement).first()

            if developer_account is None:
                developer_account = AweDeveloperAccount(
                    balance=settings.withdraw_tx_fee
                )
            else:
                developer_account.balance = AweDeveloperAccount.balance + settings.withdraw_tx_fee

            session.add(developer_account)

            # 3. Create the withdraw request

            agent_withdraw = AgentAccountWithdraw(
                user_agent_id=agent_id,
                address=user_agent.user_address,
                amount=amount
            )
            session.add(agent_withdraw)
            session.commit()
            session.refresh(agent_withdraw)

            agent_withdraw_id = agent_withdraw.id

    logger.info(f"[Withdraw To Creator] [Agent Withdraw {agent_withdraw_id}] Withdraw created!")

    # Send the transaction
    tx, last_valid_block_height = awe_on_chain.transfer_to_user(f"agent_withdraw_{agent_withdraw_id}", agent_creator_address, amount)

    logger.info(f"[Withdraw To Creator] [Agent Withdraw {agent_withdraw_id}] Tx sent! {tx}")

    # Record the tx
    with Session(engine) as session:
        statement = select(AgentAccountWithdraw).where(AgentAccountWithdraw.id == agent_withdraw_id)
        agent_withdraw = session.exec(statement).first()

        agent_withdraw.tx_hash = tx
        agent_withdraw.tx_last_valid_block_height = last_valid_block_height
        agent_withdraw.status = AgentAccountWithdrawStatus.TX_SENT

        session.add(agent_withdraw)
        session.commit()

    logger.info(f"[Withdraw To Creator] [Agent Withdraw {agent_withdraw_id}] Tx recorded!")

    return tx


def finalize_withdraw_to_creator(agent_withdraw_id: int):
    logger.info(f"[Withdraw To Creator] [Agent Withdraw {agent_withdraw_id}] finalizing agent account withdraw")

    with Session(engine) as session:
        statement = select(AgentAccountWithdraw).where(AgentAccountWithdraw.id == agent_withdraw_id)
        agent_withdraw = session.exec(statement).first()

        agent_withdraw.status = AgentAccountWithdrawStatus.SUCCESS

        session.add(agent_withdraw)
        session.commit()

    logger.info(f"[Withdraw To Creator] [Agent Withdraw {agent_withdraw_id}] Agent account withdraw finalized!")

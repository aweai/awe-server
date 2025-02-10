import logging
import signal
import time
from sqlmodel import Session, select
from awe.db import engine
from awe.models.tg_user_deposit import TgUserDeposit, TgUserDepositStatus
from awe.models.user_staking import UserStaking, UserStakingStatus
from awe.models.game_pool_charge import GamePoolCharge, GamePoolChargeStatus
from awe.models.tg_user_withdraw import TgUserWithdraw, TgUserWithdrawStatus
from awe.models.user_agent_refund import UserAgentRefund, UserAgentRefundStatus
from awe.models.agent_account_withdraw import AgentAccountWithdraw, AgentAccountWithdrawStatus
from awe.models.user_agent_staking import UserAgentStaking, UserAgentStakingStatus
from awe.agent_manager.agent_fund import finalize_user_deposit, \
                                        finalize_user_staking, \
                                        finalize_withdraw_to_user, \
                                        finalize_release_staking, \
                                        finalize_game_pool_charge, \
                                        finalize_refund_agent_staking, \
                                        finalize_withdraw_to_creator, \
                                        finalize_agent_creation_staking
from awe.blockchain import awe_on_chain
import traceback
import time

batch_size = 10
fetch_interval = 1

class PaymentProcessor:
    # Check the tx status
    # Execute the finalizing process if tx is confirmed
    # Mark failure if tx is cancelled


    def __init__(self) -> None:
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.logger = logging.getLogger("[Payment Processor]")


    def exit_gracefully(self, signum, frame):
        self.logger.info("Gracefully shutdown the payment proceesor...")
        self.kill_now = True


    def start(self):
        while not self.kill_now:
            self.logger.debug("checking pending TXs...")
            processed = 0

            processed = processed + self.process_user_deposit()
            processed = processed + self.process_user_staking()
            processed = processed + self.process_game_pool_charge()
            processed = processed + self.process_user_withdraw()
            processed = processed + self.process_release_staking()
            processed = processed + self.process_agent_refund()
            processed = processed + self.process_agent_account_withdraw()
            processed = processed + self.process_agent_creation_staking()

            if processed == 0:
                time.sleep(5)

        self.logger.info("Payment processor stopped!")


    def process_user_deposit(self) -> int:
        with Session(engine) as session:
            statement = select(TgUserDeposit).where(TgUserDeposit.status == TgUserDepositStatus.TX_SENT).order_by(TgUserDeposit.id.asc()).limit(batch_size)
            tg_user_deposits = session.exec(statement).all()
            for tg_user_deposit in tg_user_deposits:
                try:
                    self.logger.info(f"[User Deposit {tg_user_deposit.id}] Check tx status...")
                    tx_status = self.get_tx_status(tg_user_deposit.tx_hash, tg_user_deposit.tx_last_valid_block_height)
                    self.logger.info(f"[User Deposit {tg_user_deposit.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_user_deposit(tg_user_deposit.id)
                    elif tx_status == "failed":
                        TgUserDeposit.update_status(tg_user_deposit.id, TgUserDepositStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(tg_user_deposits)


    def process_user_staking(self) -> int:
        with Session(engine) as session:
            statement = select(UserStaking).where(UserStaking.status == UserStakingStatus.TX_SENT).order_by(UserStaking.id.asc()).limit(batch_size)
            user_stakings = session.exec(statement).all()
            for user_staking in user_stakings:
                try:
                    self.logger.info(f"[User Staking {user_staking.id}] Check tx status...")
                    tx_status = self.get_tx_status(user_staking.tx_hash, user_staking.tx_last_valid_block_height)
                    self.logger.info(f"[User Staking {user_staking.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_user_staking(user_staking.id)
                    elif tx_status == "failed":
                        UserStaking.update_staking_status(user_staking.id, UserStakingStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(user_stakings)


    def process_game_pool_charge(self) -> int:
        with Session(engine) as session:
            statement = select(GamePoolCharge).where(GamePoolCharge.status == GamePoolChargeStatus.TX_SENT).order_by(GamePoolCharge.id.asc()).limit(batch_size)
            game_pool_charges = session.exec(statement).all()
            for game_pool_charge in game_pool_charges:
                try:
                    self.logger.info(f"[Game Pool Charge {game_pool_charge.id}] Check tx status...")
                    tx_status = self.get_tx_status(game_pool_charge.tx_hash, game_pool_charge.tx_last_valid_block_height)
                    self.logger.info(f"[Game Pool Charge {game_pool_charge.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_game_pool_charge(game_pool_charge.id)
                    elif tx_status == "failed":
                        GamePoolCharge.update_status(game_pool_charge.id, GamePoolChargeStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(game_pool_charges)


    def process_user_withdraw(self) -> int:
        with Session(engine) as session:
            statement = select(TgUserWithdraw).where(TgUserWithdraw.status == TgUserWithdrawStatus.TX_SENT).order_by(TgUserWithdraw.id.asc()).limit(batch_size)
            tg_user_withdraws = session.exec(statement).all()
            for tg_user_withdraw in tg_user_withdraws:
                try:
                    self.logger.info(f"[User Withdraw {tg_user_withdraw.id}] Check tx status...")
                    tx_status = self.get_tx_status(tg_user_withdraw.tx_hash, tg_user_withdraw.tx_last_valid_block_height)
                    self.logger.info(f"[User Withdraw {tg_user_withdraw.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_withdraw_to_user(tg_user_withdraw.id)
                    elif tx_status == "failed":
                        TgUserWithdraw.update_status(tg_user_withdraw.id, TgUserWithdrawStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(tg_user_withdraws)


    def process_release_staking(self) -> int:
        with Session(engine) as session:
            statement = select(UserStaking).where(UserStaking.release_status == UserStakingStatus.TX_SENT).order_by(UserStaking.id.asc()).limit(batch_size)
            user_stakings = session.exec(statement).all()
            for user_staking in user_stakings:
                try:
                    self.logger.info(f"[Release User Staking {user_staking.id}] Check tx status...")
                    tx_status = self.get_tx_status(user_staking.release_tx_hash, user_staking.tx_last_valid_block_height)
                    self.logger.info(f"[Release User Staking {user_staking.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_release_staking(user_staking.id)
                    elif tx_status == "failed":
                        UserStaking.update_release_status(user_staking.id, UserStakingStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(user_stakings)


    def process_agent_refund(self) -> int:
        with Session(engine) as session:
            statement = select(UserAgentRefund).where(UserAgentRefund.status == UserAgentRefundStatus.TX_SENT).order_by(UserAgentRefund.id.asc()).limit(batch_size)
            agent_refunds = session.exec(statement).all()
            for agent_refund in agent_refunds:
                try:
                    self.logger.info(f"[Agent Refund {agent_refund.id}] Check tx status...")
                    tx_status = self.get_tx_status(agent_refund.tx_hash, agent_refund.tx_last_valid_block_height)
                    self.logger.info(f"[Release User Staking {agent_refund.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_refund_agent_staking(agent_refund.id)
                    elif tx_status == "failed":
                        UserAgentRefund.update_status(agent_refund.id, UserAgentRefund.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(agent_refunds)


    def process_agent_account_withdraw(self) -> int:
        with Session(engine) as session:
            statement = select(AgentAccountWithdraw).where(AgentAccountWithdraw.status == AgentAccountWithdrawStatus.TX_SENT).order_by(AgentAccountWithdraw.id.asc()).limit(batch_size)
            agent_withdraws = session.exec(statement).all()
            for agent_withdraw in agent_withdraws:
                try:
                    self.logger.info(f"[Agent Withdraw {agent_withdraw.id}] Check tx status...")
                    tx_status = self.get_tx_status(agent_withdraw.tx_hash, agent_withdraw.tx_last_valid_block_height)
                    self.logger.info(f"[Agent Withdraw {agent_withdraw.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_withdraw_to_creator(agent_withdraw.id)
                    elif tx_status == "failed":
                        AgentAccountWithdraw.update_status(agent_withdraw.id, AgentAccountWithdrawStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

            return len(agent_withdraws)

    def process_agent_creation_staking(self) -> int:
        with Session(engine) as session:
            statement = select(UserAgentStaking).where(UserAgentStaking.status == UserAgentStakingStatus.TX_SENT).order_by(UserAgentStaking.id.asc()).limit(batch_size)
            agent_stakings = session.exec(statement).all()
            for agent_staking in agent_stakings:
                try:
                    self.logger.info(f"[Agent Creation {agent_staking.id}] Check tx status...")
                    tx_status = self.get_tx_status(agent_staking.tx_hash, agent_staking.tx_last_valid_block_height)
                    self.logger.info(f"[Agent Creation {agent_staking.id}] Tx status {tx_status}")
                    if tx_status == "success":
                        finalize_agent_creation_staking(agent_staking.id)
                    elif tx_status == "failed":
                        UserAgentStaking.update_status(agent_staking.id, UserAgentStakingStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

                time.sleep(fetch_interval)

        return len(agent_stakings)


    def get_tx_status(self, tx_hash: str, last_valid_block_height: int) -> str:
        is_confirmed = awe_on_chain.is_tx_confirmed(tx_hash)
        if is_confirmed:
            return "success"

        # Not confirmed
        # Check if the tx is expired
        current_block_height = awe_on_chain.get_block_height()

        self.logger.debug(f"Current block height: {current_block_height}/{last_valid_block_height}")

        if current_block_height > last_valid_block_height + 30:
            return "failed"

        # Still waiting
        return "pending"

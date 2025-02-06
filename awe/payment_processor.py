import logging
import signal
import time
from sqlmodel import Session, select
from awe.db import engine
from awe.models.tg_user_deposit import TgUserDeposit, TgUserDepositStatus
from awe.models.user_staking import UserStaking, UserStakingStatus
from awe.models.game_pool_charge import GamePoolCharge, GamePoolChargeStatus
from awe.agent_manager.agent_fund import finalize_user_payment, finalize_user_staking
from awe.api.routers.v1.user_agents import finalize_game_pool_charge
from awe.blockchain import awe_on_chain
import traceback

batch_size = 10

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

            processed = 0

            processed = processed + self.process_user_deposit()
            processed = processed + self.process_user_staking()
            processed = processed + self.process_game_pool_charge()
            processed = processed + self.process_user_withdraw()
            processed = processed + self.process_return_staking()

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
                        finalize_user_payment(tg_user_deposit.id)
                    elif tx_status == "failed":
                        TgUserDeposit.update_user_deposit_status(tg_user_deposit.id, TgUserDepositStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

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

            return len(game_pool_charges)


    def process_user_withdraw(self) -> int:
        return 0


    def process_return_staking(self) -> int:
        return 0


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

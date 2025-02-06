import logging
import signal
import time
from sqlmodel import Session, select
from awe.db import engine
from awe.models.tg_user_deposit import TgUserDeposit, TgUserDepositStatus
from awe.agent_manager.agent_fund import finalize_user_payment
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
                    tx_status = self.get_tx_status(tg_user_deposit.tx_hash, tg_user_deposit.tx_last_valid_block_height)
                    if tx_status == "success":
                        finalize_user_payment(tg_user_deposit.id)
                    elif tx_status == "failed":
                        TgUserDeposit.update_user_deposit_status(tg_user_deposit.id, TgUserDepositStatus.FAILED)
                except Exception as e:
                    self.logger.error(e)
                    self.logger.error(traceback.format_exc())

            return len(tg_user_deposits)


    def process_user_staking(self) -> int:
        return 0


    def process_game_pool_charge(self) -> int:
        return 0


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
        if current_block_height > last_valid_block_height + 30:
            return "failed"

        # Still waiting
        return "pending"

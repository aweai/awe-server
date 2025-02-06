from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Optional, Annotated
from typing_extensions import Self
from awe.db import engine
from .user_agent_data import UserAgentData

class TgUserDepositStatus:
    APPROVING = 1
    APPROVED = 2
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6


class TgUserDeposit(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    user_agent_round: int = Field(nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    approve_tx_hash: str = Field(nullable=True)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=TgUserDepositStatus.APPROVING, index=True)] = TgUserDepositStatus.APPROVING

    @classmethod
    def get_user_deposit_for_latest_round(cls, user_agent_id: int, tg_user_id: str) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(TgUserDeposit, UserAgentData).where(
                TgUserDeposit.user_agent_id == UserAgentData.user_agent_id,
                TgUserDeposit.user_agent_id == user_agent_id,
                TgUserDeposit.tg_user_id == tg_user_id,
                TgUserDeposit.user_agent_round == UserAgentData.current_round,
                TgUserDeposit.tx_hash.is_not(None),
                TgUserDeposit.tx_hash != ""
                )
            result = session.exec(statement).first()
            if result is None:
                return None

            tg_user_deposit, _ = result
            return tg_user_deposit

    @classmethod
    def update_user_deposit_status(cls, user_deposit_id: int, status: int):
        with Session(engine) as session:
            statement = select(TgUserDeposit).where(TgUserDeposit.id == user_deposit_id)
            tg_user_deposit = session.exec(statement).first()
            tg_user_deposit.status = status
            session.add(tg_user_deposit)
            session.commit()

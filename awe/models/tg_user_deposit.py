from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from awe.db import engine

class TgUserDepositStatus:
    APPROVING = 1
    APPROVED = 2
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6


class TgUserDeposit(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    tg_user_id: str = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    approve_tx_hash: str = Field(nullable=True)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=TgUserDepositStatus.APPROVING, index=True)] = TgUserDepositStatus.APPROVING

    @classmethod
    def update_status(cls, user_deposit_id: int, status: int):
        with Session(engine) as session:
            statement = select(TgUserDeposit).where(TgUserDeposit.id == user_deposit_id)
            tg_user_deposit = session.exec(statement).first()
            tg_user_deposit.status = status
            session.add(tg_user_deposit)
            session.commit()

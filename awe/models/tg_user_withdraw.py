from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from sqlmodel import Session, select
from awe.db import engine

class TgUserWithdrawStatus:
    CREATED = 1
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6

class TgUserWithdraw(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    user_agent_round: int = Field(nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=TgUserWithdrawStatus.CREATED, index=True)] = TgUserWithdrawStatus.CREATED

    @classmethod
    def update_status(cls, user_withdraw_id: int, status: int):
        with Session(engine) as session:
            statement = select(TgUserWithdraw).where(TgUserWithdraw.id == user_withdraw_id)
            tg_user_withdraw = session.exec(statement).first()
            tg_user_withdraw.status = status
            session.add(tg_user_withdraw)
            session.commit()

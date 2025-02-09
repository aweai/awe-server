from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from sqlmodel import Session, select
from awe.db import engine

class AgentAccountWithdrawStatus:
    CREATED = 1
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6

class AgentAccountWithdraw(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=AgentAccountWithdrawStatus.CREATED, index=True)] = AgentAccountWithdrawStatus.CREATED

    @classmethod
    def update_status(cls, agent_account_withdraw_id: int, status: int):
        with Session(engine) as session:
            statement = select(AgentAccountWithdraw).where(AgentAccountWithdraw.id == agent_account_withdraw_id)
            agent_account_withdraw = session.exec(statement).first()
            agent_account_withdraw.status = status
            session.add(agent_account_withdraw)
            session.commit()

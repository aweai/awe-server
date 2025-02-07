from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from awe.db import engine


class UserAgentRefundStatus:
    CREATED = 1
    TX_SENT = 3
    FAILED = 5
    SUCCESS = 6


class UserAgentRefund(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=UserAgentRefundStatus.CREATED, index=True)] = UserAgentRefundStatus.CREATED

    @classmethod
    def update_status(cls, refund_id: int, status: int):
        with Session(engine) as session:
            statement = select(UserAgentRefund).where(UserAgentRefund.id == refund_id)
            agent_refund = session.exec(statement).first()
            agent_refund.status = status
            session.add(agent_refund)
            session.commit()

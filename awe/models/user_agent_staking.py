from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from awe.db import engine

class UserAgentStakingStatus:
    APPROVING = 1
    APPROVED = 2
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6


class UserAgentStaking(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    address: str = Field(nullable=False, index=True)
    amount: int = Field(nullable=False)
    approve_tx_hash: str = Field(nullable=True)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=UserAgentStakingStatus.APPROVING, index=True)] = UserAgentStakingStatus.APPROVING

    @classmethod
    def update_status(cls, user_agent_staking_id: int, status: int):
        with Session(engine) as session:
            statement = select(UserAgentStaking).where(UserAgentStaking.id == user_agent_staking_id)
            user_agent_staking = session.exec(statement).first()
            user_agent_staking.status = status
            session.add(user_agent_staking)
            session.commit()

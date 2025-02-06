from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Annotated
from awe.db import engine


class GamePoolChargeStatus:
    APPROVING = 1
    APPROVED = 2
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6


class GamePoolCharge(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    approve_tx_hash: Annotated[str, Field(nullable=True)]
    tx_hash: Annotated[str, Field(nullable=True)]
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=GamePoolChargeStatus.APPROVING, index=True)] = GamePoolChargeStatus.APPROVING


    @classmethod
    def update_status(cls, game_pool_charge_id: int, status: int):
        with Session(engine) as session:
            statement = select(GamePoolCharge).where(GamePoolCharge.id == game_pool_charge_id)
            game_pool_charge = session.exec(statement).first()
            game_pool_charge.status = status
            session.add(game_pool_charge)
            session.commit()

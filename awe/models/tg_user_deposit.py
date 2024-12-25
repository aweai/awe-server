from sqlmodel import SQLModel, Field, Session, select
from .utils import unix_timestamp_in_seconds
from typing import Optional
from typing_extensions import Self
from awe.db import engine
from .user_agent_data import UserAgentData

class TgUserDeposit(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    user_agent_round: int = Field(nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=False)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)

    @classmethod
    def get_user_deposit_for_latest_round(cls, user_agent_id: int, tg_user_id: str) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(TgUserDeposit, UserAgentData).where(
                TgUserDeposit.user_agent_id == UserAgentData.user_agent_id,
                TgUserDeposit.user_agent_id == user_agent_id,
                TgUserDeposit.tg_user_id == tg_user_id,
                TgUserDeposit.user_agent_round == UserAgentData.current_round
                )
            tg_user_deposit, _ = session.exec(statement).first()
            return tg_user_deposit

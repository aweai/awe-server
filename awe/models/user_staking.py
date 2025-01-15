from sqlmodel import SQLModel, Field, select, Session
from .utils import unix_timestamp_in_seconds
from typing import List
from typing_extensions import Self
from awe.db import engine
from .utils import unix_timestamp_in_seconds

class UserStaking(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=False)
    release_tx_hash: str = Field(nullable=True)
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)
    released_at: int = Field(nullable=True)

    @classmethod
    def get_user_staking_list(cls, user_agent_id: int, tg_user_id: str) -> List[Self]:
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == user_agent_id,
                UserStaking.released_at.is_(None)
            ).order_by(UserStaking.created_at.asc())

            return session.exec(statement).all()

    def get_multiplier(self, till_day_timestamp: int) -> float:

        period = till_day_timestamp - self.created_at

        if period >= 12 * 30 * 86400:
            return 3

        if period >= 6 * 30 * 86400:
            return 2

        if period >= 3 * 30 * 86400:
            return 1.5

        return 1

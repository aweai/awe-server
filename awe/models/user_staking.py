from sqlmodel import SQLModel, Field, select, Session
from .utils import unix_timestamp_in_seconds
from typing import List, Optional
from typing_extensions import Self
from awe.db import engine

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

    @classmethod
    def get_user_staking(cls, staking_id: int, user_agent_id: int, tg_user_id: str) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.id == staking_id,
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == user_agent_id,
                UserStaking.released_at.is_(None)
            )

            return session.exec(statement).first()

    @classmethod
    def release_user_staking(cls, staking_id: int, user_agent_id: int, tg_user_id: str):
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.id == staking_id,
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == user_agent_id,
                UserStaking.released_at.is_(None)
            )

            user_staking = session.exec(statement).first()

            if user_staking is None:
                raise Exception(f"User staking not found: {staking_id}")

            user_staking.released_at = unix_timestamp_in_seconds()
            session.add(user_staking)
            session.commit()

    @classmethod
    def record_releasing_user_staking_tx(cls, staking_id: int, user_agent_id: int, tg_user_id: str, tx_hash: str):
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.id == staking_id,
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == user_agent_id
            )

            user_staking = session.exec(statement).first()

            if user_staking is None:
                raise Exception(f"User staking not found: {staking_id}")

            user_staking.release_tx_hash = tx_hash
            session.add(user_staking)
            session.commit()

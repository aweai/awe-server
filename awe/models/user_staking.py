from sqlmodel import SQLModel, Field, select, Session, or_
from .utils import unix_timestamp_in_seconds
from typing import List, Annotated
from typing_extensions import Self
from awe.db import engine
from .utils import unix_timestamp_in_seconds

class UserStakingStatus:
    APPROVING = 1
    APPROVED = 2
    TX_SENT = 3
    TX_CONFIRMED = 4
    FAILED = 5
    SUCCESS = 6


class UserStaking(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    address: Annotated[str, Field(nullable=True)]
    amount: int = Field(nullable=False)
    approve_tx_hash: str = Field(nullable=True)
    tx_hash: str = Field(nullable=True)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)
    tx_last_valid_block_height: Annotated[int, Field(nullable=True)]
    status: Annotated[int, Field(default=UserStakingStatus.APPROVING, index=True)] = UserStakingStatus.APPROVING

    release_tx_hash: str = Field(nullable=True)
    release_status: Annotated[int, Field(index=True, nullable=True)]
    released_at: int = Field(nullable=True)


    @classmethod
    def get_user_staking_list(cls, user_agent_id: int, tg_user_id: str) -> List[Self]:
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.tg_user_id == tg_user_id,
                UserStaking.user_agent_id == user_agent_id,
                or_(
                    UserStaking.release_status.is_(None),
                    UserStaking.release_status != UserStakingStatus.SUCCESS
                )
            ).order_by(UserStaking.created_at.asc())

            return session.exec(statement).all()


    @classmethod
    def update_staking_status(cls, user_staking_id: int, status: UserStakingStatus):
        with Session(engine) as session:
            statement = select(UserStaking).where(UserStaking.id == user_staking_id)
            user_staking = session.exec(statement).first()
            user_staking.status = status
            session.add(user_staking)
            session.commit()


    @classmethod
    def update_release_status(cls, user_staking_id: int, status: UserStakingStatus):
        with Session(engine) as session:
            statement = select(UserStaking).where(UserStaking.id == user_staking_id)
            user_staking = session.exec(statement).first()
            user_staking.release_status = status
            session.add(user_staking)
            session.commit()


    def get_multiplier(self, till_day_timestamp: int) -> float:

        period = till_day_timestamp - self.created_at

        if period >= 12 * 30 * 86400:
            return 3

        if period >= 6 * 30 * 86400:
            return 2

        if period >= 3 * 30 * 86400:
            return 1.5

        return 1

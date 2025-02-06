from sqlmodel import SQLModel, Field, select, Session
from typing import Annotated, Optional
from awe.db import engine
from .utils import get_day_as_timestamp

class UserAgentStatsStakingDailyCounts(SQLModel, table=True):
    id: Annotated[Optional[int], Field(primary_key=True, default=None)]
    day: Annotated[int, Field(index=True)]
    user_agent_id: Annotated[int, Field(index=True)]
    in_amount: Annotated[int, Field(default=0)] = 0
    out_amount: Annotated[int, Field(default=0)] = 0

    @classmethod
    def add_staking(cls, user_agent_id: int, amount: int, session: Session):

        day = get_day_as_timestamp()

        statement = select(UserAgentStatsStakingDailyCounts).where(
            UserAgentStatsStakingDailyCounts.day == day,
            UserAgentStatsStakingDailyCounts.user_agent_id == user_agent_id
        )
        stats_data = session.exec(statement).first()

        if stats_data is None:
            stats_data = UserAgentStatsStakingDailyCounts(
                day=day,
                user_agent_id=user_agent_id,
                in_amount=amount
            )
        else:
            stats_data.in_amount = UserAgentStatsStakingDailyCounts.in_amount + amount

        session.add(stats_data)


    @classmethod
    def add_releasing(cls, user_agent_id: int, amount: int):
        day = get_day_as_timestamp()

        with Session(engine) as session:
            statement = select(UserAgentStatsStakingDailyCounts).where(
                UserAgentStatsStakingDailyCounts.day == day,
                UserAgentStatsStakingDailyCounts.user_agent_id == user_agent_id
            )
            stats_data = session.exec(statement).first()

            if stats_data is None:
                stats_data = UserAgentStatsStakingDailyCounts(
                    day=day,
                    user_agent_id=user_agent_id,
                    out_amount=amount
                )
            else:
                stats_data.out_amount = UserAgentStatsStakingDailyCounts.out_amount + amount

            session.add(stats_data)
            session.commit()

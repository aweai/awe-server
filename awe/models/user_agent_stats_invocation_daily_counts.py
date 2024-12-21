from sqlmodel import SQLModel, Field, Session, select
from awe.db import engine
from .utils import get_day_as_timestamp


class UserAgentStatsInvocationDailyCounts(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    day: int = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    tool: str = Field(index=True, nullable=False)
    invocations: int = Field(nullable=False, default=0)

    @classmethod
    def add_invocation(cls, user_agent_id: int, tool: str):

        # Update the invocation count for today
        day = get_day_as_timestamp()

        with Session(engine) as session:
            statement = select(UserAgentStatsInvocationDailyCounts).where(
                UserAgentStatsInvocationDailyCounts.day == day,
                UserAgentStatsInvocationDailyCounts.user_agent_id == user_agent_id,
                UserAgentStatsInvocationDailyCounts.tool == tool
            )
            user_agent_stats = session.exec(statement).first()

            if user_agent_stats is None:
                user_agent_stats = UserAgentStatsInvocationDailyCounts(
                    day=day,
                    user_agent_id=user_agent_id,
                    tool=tool,
                    invocations=1
                )
            else:
                user_agent_stats.invocations = UserAgentStatsInvocationDailyCounts.invocations + 1

            session.add(user_agent_stats)
            session.commit()

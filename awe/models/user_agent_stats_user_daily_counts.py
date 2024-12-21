from sqlmodel import SQLModel, Field, Session, select
from awe.db import engine

class UserAgentStatsUserDailyCounts(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    day: int = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    users: int = Field(default=0)


    @classmethod
    def add_user(cls, day: int, user_agent_id: int):

        with Session(engine) as session:
            statement = select(UserAgentStatsUserDailyCounts).where(
                UserAgentStatsUserDailyCounts.day == day,
                UserAgentStatsUserDailyCounts.user_agent_id == user_agent_id
            )
            user_stats = session.exec(statement).first()

            if user_stats is None:
                user_stats = UserAgentStatsUserDailyCounts(
                    day=day,
                    user_agent_id=user_agent_id,
                    users=1
                )
            else:
                user_stats.users = UserAgentStatsUserDailyCounts.users + 1

            session.add(user_stats)
            session.commit()

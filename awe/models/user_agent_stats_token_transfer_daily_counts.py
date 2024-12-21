
from sqlmodel import SQLModel, Field, Session, select
from awe.db import engine
from .utils import get_day_as_timestamp

class UserAgentStatsTokenTransferDailyCounts(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    day: int = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    transactions: int = Field(default=0)
    amount: int = Field(default=0)
    addresses: int = Field(default=0)

    @classmethod
    def add_transfer(cls, user_agent_id: int, amount: int, is_new_address: bool):
        # Update the invocation count for today
        day = get_day_as_timestamp()

        with Session(engine) as session:
            statement = select(UserAgentStatsTokenTransferDailyCounts).where(
                UserAgentStatsTokenTransferDailyCounts.day == day,
                UserAgentStatsTokenTransferDailyCounts.user_agent_id == user_agent_id
            )
            stats_data = session.exec(statement).first()

            if stats_data is None:
                stats_data = UserAgentStatsTokenTransferDailyCounts(
                    day=day,
                    user_agent_id=user_agent_id,
                    transactions=1,
                    amount=amount,
                    addresses=1
                )
            else:
                stats_data.transactions = UserAgentStatsTokenTransferDailyCounts.transactions + 1
                stats_data.amount = UserAgentStatsTokenTransferDailyCounts.amount + amount

                if is_new_address:
                    stats_data.addresses = UserAgentStatsTokenTransferDailyCounts.addresses + 1

            session.add(stats_data)
            session.commit()

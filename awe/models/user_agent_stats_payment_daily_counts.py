
from sqlmodel import SQLModel, Field, Session, select
from .utils import get_day_as_timestamp

class UserAgentStatsPaymentDailyCounts(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    day: int = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    transactions: int = Field(default=0)
    creator_amount: int = Field(default=0)
    pool_amount: int = Field(default=0)
    addresses: int = Field(default=0)

    @classmethod
    def add_payment(cls, user_agent_id: int, pool_amount: int, creator_amount: int, session: Session):
        # Update the invocation count for today
        day = get_day_as_timestamp()

        statement = select(UserAgentStatsPaymentDailyCounts).where(
            UserAgentStatsPaymentDailyCounts.day == day,
            UserAgentStatsPaymentDailyCounts.user_agent_id == user_agent_id
        )
        stats_data = session.exec(statement).first()

        if stats_data is None:
            stats_data = UserAgentStatsPaymentDailyCounts(
                day=day,
                user_agent_id=user_agent_id,
                transactions=1,
                pool_amount=pool_amount,
                creator_amount=creator_amount,
                addresses=1
            )
        else:
            stats_data.transactions = UserAgentStatsPaymentDailyCounts.transactions + 1

            if pool_amount != 0:
                stats_data.pool_amount = UserAgentStatsPaymentDailyCounts.pool_amount + pool_amount

            if creator_amount != 0:
                stats_data.creator_amount = UserAgentStatsPaymentDailyCounts.creator_amount + creator_amount

        session.add(stats_data)

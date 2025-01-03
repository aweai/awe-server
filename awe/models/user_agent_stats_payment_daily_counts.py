
from sqlmodel import SQLModel, Field, Session, select
from awe.db import engine
from .utils import get_day_as_timestamp
from awe.settings import settings

class UserAgentStatsPaymentDailyCounts(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    day: int = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    transactions: int = Field(default=0)
    creator_amount: int = Field(default=0)
    pool_amount: int = Field(default=0)
    addresses: int = Field(default=0)

    @classmethod
    def add_payment(cls, user_agent_id: int, amount: int, is_new_address: bool):
        # Update the invocation count for today
        day = get_day_as_timestamp()

        pool_amount, creator_amount, _ = settings.tn_share_user_payment(amount)

        with Session(engine) as session:
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
                stats_data.pool_amount = UserAgentStatsPaymentDailyCounts.pool_amount + pool_amount
                stats_data.creator_amount = UserAgentStatsPaymentDailyCounts.creator_amount + creator_amount

                if is_new_address:
                    stats_data.addresses = UserAgentStatsPaymentDailyCounts.addresses + 1

            session.add(stats_data)
            session.commit()

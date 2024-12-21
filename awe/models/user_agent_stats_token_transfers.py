from sqlmodel import SQLModel, Field, Column, BigInteger, Session, select
from awe.db import engine
from awe.models.user_agent_data import UserAgentData
from awe.models.user_agent_stats_token_transfer_daily_counts import UserAgentStatsTokenTransferDailyCounts
from typing import Tuple
from awe.cache import cache
from .utils import unix_timestamp_in_seconds, get_day_as_timestamp

class AddressSet:

    def iterate_query(self, statement, redis_key):
        page_size = 10000
        current_page = 0

        while(True):
            with Session(engine) as session:
                current_statement = statement.offset(current_page * page_size).limit(page_size)
                addresses = session.exec(current_statement).all()

                if len(addresses) > 0:
                    cache.sadd(redis_key, *addresses)

                if len(addresses) < page_size:
                    return

                current_page += 1

    def load_addresses_from_db_for_today(self, day: int, user_agent_id: int, redis_key: str):

        statement = select(UserAgentStatsTokenTransfers.to_address).distinct().where(
                UserAgentStatsTokenTransfers.user_agent_id == user_agent_id,
                UserAgentStatsTokenTransfers.created_at >= day
            ).order_by(UserAgentStatsTokenTransfers.id.asc())

        self.iterate_query(statement, redis_key)

    def load_addresses_from_db_total(self, user_agent_id: int, redis_key: str) -> list[str]:
        statement = select(UserAgentStatsTokenTransfers.to_address).distinct().where(
                    UserAgentStatsTokenTransfers.user_agent_id == user_agent_id
                ).order_by(UserAgentStatsTokenTransfers.id.asc())

        self.iterate_query(statement, redis_key)

    def add_address(self, day: int, user_agent_id: int, address: str) -> Tuple[bool, bool]:
        today_addresses_keys = "AGENT_STATS_ADDRESSES_" + str(day) + "_" + str(user_agent_id)
        total_addresses_keys = "AGENT_STATS_ADDRESSES_TOTAL_" + str(user_agent_id)

        # Check if the data exists in redis
        today_addresses = cache.scard(today_addresses_keys)
        if today_addresses == 0:
            self.load_addresses_from_db_for_today(day, user_agent_id, today_addresses_keys)

        total_addresses = cache.scard(total_addresses_keys)
        if total_addresses == 0:
            self.load_addresses_from_db_total(user_agent_id, total_addresses_keys)

        today_incremented = cache.sadd(today_addresses_keys, address)
        total_incremented = cache.sadd(total_addresses_keys, address)

        return today_incremented==1, total_incremented==1


addressSet = AddressSet()

class UserAgentStatsTokenTransfers(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    user_agent_id: int = Field(nullable=False)
    tg_user_id: str = Field(nullable=False)
    to_address: str = Field(nullable=False)
    transfer_amount: int = Field(sa_column=Column(BigInteger()))
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)

    @classmethod
    def add_invocation(cls, user_agent_id: int, tg_user_id: str, to_address: str, amount: int):

        day = get_day_as_timestamp()
        is_new_address_today, is_new_address_total = addressSet.add_address(day, user_agent_id, to_address)

        # Add token transfer daily count
        UserAgentStatsTokenTransferDailyCounts.add_transfer(user_agent_id, amount, is_new_address_today)

        # Add token transfer total count
        UserAgentData.add_awe_token_transfer_stats(user_agent_id, amount, is_new_address_total)

        # Log the raw transfer data
        with Session(engine) as session:
            log = UserAgentStatsTokenTransfers(
                user_agent_id=user_agent_id,
                tg_user_id=tg_user_id,
                to_address=to_address,
                transfer_amount=amount
            )

            session.add(log)
            session.commit()

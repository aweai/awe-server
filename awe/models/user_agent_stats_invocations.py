from sqlmodel import SQLModel, Field, Session, select
from enum import Enum
from awe.db import engine
from .user_agent_stats_invocation_daily_counts import UserAgentStatsInvocationDailyCounts
from .user_agent_stats_user_daily_counts import UserAgentStatsUserDailyCounts
from awe.models.user_agent_data import UserAgentData
from awe.cache import cache
from typing import Tuple
from .utils import get_day_as_timestamp, unix_timestamp_in_seconds
import logging

logger = logging.getLogger("[Stats Invocations]")

class AITools(str, Enum):
    LLM = 'LLM'
    SD = 'SD'
    TOKEN_QUERY = 'TOKEN_QUERY'
    TOKEN_TRANSFER = 'TOKEN_TRANSFER'

class UsersIdSet:

    def iterate_query(self, statement, redis_key):
        page_size = 10000
        current_page = 0

        while(True):
            logger.debug(f"Querying DB to load existing user ids...page {current_page}")
            with Session(engine) as session:
                current_statement = statement.offset(current_page * page_size).limit(page_size)
                user_ids = session.exec(current_statement).all()

                logger.debug(f"Loaded {len(user_ids)} user_ids")

                if len(user_ids) > 0:
                    logger.debug(f"Adding user_ids to redis: {user_ids}")
                    cache.sadd(redis_key, *user_ids)

                if len(user_ids) < page_size:
                    return

                current_page += 1

    def load_user_ids_from_db_for_today(self, day: int, user_agent_id: int, redis_key: str):

        statement = select(UserAgentStatsInvocations.tg_user_id).distinct().where(
                UserAgentStatsInvocations.user_agent_id == user_agent_id,
                UserAgentStatsInvocations.created_at >= day
            ).order_by(UserAgentStatsInvocations.id.asc())

        self.iterate_query(statement, redis_key)

    def load_user_ids_from_db_total(self, user_agent_id: int, redis_key: str) -> list[str]:
        statement = select(UserAgentStatsInvocations.tg_user_id).distinct().where(
                    UserAgentStatsInvocations.user_agent_id == user_agent_id
                ).order_by(UserAgentStatsInvocations.id.asc())

        self.iterate_query(statement, redis_key)

    def add_user(self, day: int, user_agent_id: int, user_id: str) -> Tuple[bool, bool]:

        logger.debug(f"adding user stats: {user_id}")

        today_users_keys = "AGENT_STATS_USERS_" + str(day) + "_" + str(user_agent_id)
        total_users_keys = "AGENT_STATS_USERS_TOTAL_" + str(user_agent_id)

        # Check if the data exists in redis
        today_members = cache.scard(today_users_keys)
        if today_members == 0:
            logger.debug("today members zero from redis, load it from DB")
            self.load_user_ids_from_db_for_today(day, user_agent_id, today_users_keys)

        total_members = cache.scard(total_users_keys)
        if total_members == 0:
            logger.debug("total members zero from redis, load it from DB")
            self.load_user_ids_from_db_total(user_agent_id, total_users_keys)

        today_incremented = cache.sadd(today_users_keys, user_id)
        total_incremented = cache.sadd(total_users_keys, user_id)

        return today_incremented==1, total_incremented==1


usersIdSet = UsersIdSet()

class UserAgentStatsInvocations(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    user_agent_id: int = Field(index=True, nullable=False)
    tg_user_id: str = Field(index=True, nullable=False)
    tool: str = Field(nullable=False)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)

    @classmethod
    def add_invocation(cls, user_agent_id: int, tg_user_id: str, tool: AITools):

        # Update the invocation daily counts
        UserAgentStatsInvocationDailyCounts.add_invocation(user_agent_id, tool)

        # Update the invocation total counts
        UserAgentData.add_invocation(user_agent_id)

        day = get_day_as_timestamp()

        # Update the user daily and total counts
        is_daily_new_user, is_total_new_user = usersIdSet.add_user(day, user_agent_id, tg_user_id)

        if is_daily_new_user:
            UserAgentStatsUserDailyCounts.add_user(day, user_agent_id)

        if is_total_new_user:
            UserAgentData.add_user(user_agent_id)

        # Save the raw log
        with Session(engine) as session:
            log = UserAgentStatsInvocations(
                user_agent_id=user_agent_id,
                tg_user_id=tg_user_id,
                tool= tool
            )

            session.add(log)
            session.commit()

from awe.db import engine
from sqlmodel import Session, select
from awe.cache import cache
import logging
from typing import Tuple

class CachedDistinctItemSet:
    def __init__(self, key_prefix: str, model, model_attr):
        self.model = model
        self.model_attr = model_attr
        self.key_prefix = key_prefix
        self.logger = logging.getLogger(f"[CachedDistinceItemSet][{key_prefix}]")

    def iterate_query(self, statement, redis_key):
        page_size = 1000
        current_page = 0

        while(True):
            with Session(engine) as session:
                current_statement = statement.offset(current_page * page_size).limit(page_size)
                items = session.exec(current_statement).all()

                if len(items) > 0:
                    addresses = [item[0] for item in items]
                    try:
                        cache.sadd(redis_key, *addresses)
                    except Exception as e:
                        self.logger.error(e)
                        raise Exception("Error writing to Redis cache")

                if len(items) < page_size:
                    return

                current_page += 1

    def load_items_from_db_for_today(self, day: int, user_agent_id: int, redis_key: str):

        statement = select(self.model_attr, self.model.id).distinct().where(
                self.model.user_agent_id == user_agent_id,
                self.model.created_at >= day,
                self.model.status == 6
            ).order_by(self.model.id.asc())

        self.iterate_query(statement, redis_key)

    def load_items_from_db_total(self, user_agent_id: int, redis_key: str) -> list[str]:
        statement = select(self.model_attr, self.model.id).distinct().where(
                    self.model.user_agent_id == user_agent_id,
                    self.model.status == 6
                ).order_by(self.model.id.asc())

        self.iterate_query(statement, redis_key)

    def add_item(self, day: int, user_agent_id: int, item: str) -> Tuple[bool, bool]:
        today_items_keys = f"AGENT_STATS_ITEMS_{self.key_prefix}_{day}_{user_agent_id}"
        total_items_keys = f"AGENT_STATS_ITEMS_{self.key_prefix}_TOTAL_{user_agent_id}"

        # Check if the data exists in redis

        try:
            today_addresses = cache.scard(today_items_keys)
        except Exception as e:
            self.logger.error(e)
            raise Exception("Error reading from Redis cache")

        if today_addresses == 0:
            self.load_items_from_db_for_today(day, user_agent_id, today_items_keys)

        try:
            total_addresses = cache.scard(total_items_keys)
        except Exception as e:
            self.logger.error(e)
            raise Exception("Error reading from Redis cache")

        if total_addresses == 0:
            self.load_items_from_db_total(user_agent_id, total_items_keys)

        today_incremented = cache.sadd(today_items_keys, item)
        total_incremented = cache.sadd(total_items_keys, item)

        return today_incremented==1, total_incremented==1

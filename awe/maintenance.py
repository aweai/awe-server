
from awe.cache import cache
import asyncio
import logging

logger = logging.getLogger("[Maintenance]")

maintenance_key = "AWE_SYSTEM_MAINTENANCE"

def is_in_maintenance_sync() -> bool:
    in_maintenance = cache.get(maintenance_key)
    logger.debug(in_maintenance)
    return in_maintenance is not None

async def is_in_maintenance() -> bool:
    return await asyncio.to_thread(is_in_maintenance_sync)

def start_maintenance():
    logger.warning("Entering maintenance mode")
    cache.set(maintenance_key, 1)

def stop_maintenance():
    logger.warning("Exiting maintenance mode")
    cache.delete(maintenance_key)

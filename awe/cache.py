from awe.settings import settings
import redis

cache = redis.from_url(settings.redis_cache, socket_timeout=3, socket_connect_timeout=3)

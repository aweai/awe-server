import redis
import os

cache_str = os.getenv("REDIS_CACHE", "")

if cache_str == "":
    raise Exception("Cache config is not provided!")

cache = redis.from_url(cache_str)

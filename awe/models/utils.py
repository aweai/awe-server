from datetime import datetime
import time

def get_day_as_timestamp() -> int:
    now = datetime.now()
    day = now.replace(hour=0,minute=0,second=0,microsecond=0)
    return int(day.timestamp())

def unix_timestamp_in_seconds() -> int:
    return int(time.time())

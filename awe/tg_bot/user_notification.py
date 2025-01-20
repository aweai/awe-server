import json
from awe.cache import cache

def send_user_notification(cls, user_agent_id: str, tg_user_id: str, msg: str):
    bot_key = f"TG_BOT_USER_NOTIFICATIONS_{user_agent_id}"
    message = json.dumps([tg_user_id, msg])
    cache.rpush(bot_key, message)

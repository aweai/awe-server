
from awe.awe_agent.awe_agent import AweAgent
from ..models.tg_bot import TGBot

class BaseHandler:
    def __init__(self, user_agent_id: int, tg_bot_config: TGBot, awe_agent: AweAgent):
        self.user_agent_id = user_agent_id
        self.tg_bot_config = tg_bot_config
        self.awe_agent = awe_agent

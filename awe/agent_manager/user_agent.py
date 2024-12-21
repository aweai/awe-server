from awe.awe_agent.awe_agent import AweAgent
from awe.tg_bot.tg_bot import TGBot
from ..models import UserAgent as UserAgentConfig
import logging

class UserAgent:
    def __init__(self, config: UserAgentConfig) -> None:
        self.user_agent_config = config
        self.logger = logging.getLogger("[User Agent]")

        if config.tg_bot.username is not None and config.tg_bot.username != "":
            self.user_agent_config.awe_agent.llm_config.prompt_preset = self.user_agent_config.awe_agent.llm_config.prompt_preset + f"\nYou will be mentioned in the chat using name '{config.tg_bot.username}'\n"

        self.awe_agent = AweAgent(user_agent_id=config.id, config=self.user_agent_config.awe_agent)

    def start_tg_bot(self) -> None:
        if self.user_agent_config.tg_bot.token is None or self.user_agent_config.tg_bot.token == "":
            self.logger.warning(f"Bot won't start: token is not set for {self.user_agent_config.tg_bot.username} of user: {self.user_agent_config.user_address}")
            return
        self.tg_bot = TGBot(self.awe_agent, self.user_agent_config.tg_bot, self.user_agent_config.id)
        self.tg_bot.start()

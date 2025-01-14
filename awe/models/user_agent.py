from typing import Optional, Annotated
from sqlmodel import SQLModel, Field, Column, Relationship
from awe.models.awe_agent import AweAgent, AweAgentSAType
from awe.models.tg_bot import TGBot, TGBotSAType
from .utils import unix_timestamp_in_seconds
from awe.models.user_agent_data import UserAgentData

class UserAgent(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    name: str = Field(default="New AI Meme")
    user_address: str = Field(index=True)
    staking_amount: int = Field(nullable=True)
    tg_bot: Optional[TGBot] = Field(sa_column=Column(TGBotSAType))
    awe_agent: Optional[AweAgent] = Field(sa_column=Column(AweAgentSAType))
    enabled: bool = Field(default=False)
    score: Annotated[int, Field(nullable=False, default=0)] = 0

    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)
    updated_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)
    deleted_at: Optional[int] = Field(nullable=True)

    agent_data: Optional[UserAgentData] = Relationship(sa_relationship_kwargs={"lazy": "select"})


    def validate_for_save(self) -> str:
        if self.name == "":
            return "Name cannot be blank!"
        return ""

    def validate_for_enable(self) -> str:

        if self.name == "":
            return "Name cannot be blank!"

        # TG Bot
        if self.tg_bot is None:
            return "Telegram Bot is not fully configured!"

        if self.tg_bot.username == "" or self.tg_bot.token == "" or self.tg_bot.start_message == "":
            return "Telegram Bot is not fully configured!"

        # Prompt
        if self.awe_agent is None or self.awe_agent.llm_config is None or self.awe_agent.llm_config.prompt_preset == "":
            return "LLM is not fully configured!"

        # Token Distribution
        if self.awe_agent.awe_token_enabled:
            if self.awe_agent.awe_token_config is None \
                or self.awe_agent.awe_token_config.max_token_per_round <= 0 \
                or self.awe_agent.awe_token_config.max_token_per_tx <= 0 \
                or self.awe_agent.awe_token_config.max_invocation_per_payment < 0 \
                or self.awe_agent.awe_token_config.max_payment_per_round < 0 \
                or self.awe_agent.awe_token_config.user_price < 10 \
                or self.awe_agent.awe_token_config.game_pool_division < 0 \
                or self.awe_agent.awe_token_config.game_pool_division > 100:

                return "Token Distribution is not fully configured!"

        # Image Generation
        if self.awe_agent.image_generation_enabled:
            if "base_model" not in self.awe_agent.image_generation_args or "name" not in self.awe_agent.image_generation_args["base_model"] or self.awe_agent.image_generation_args["base_model"]["name"] == "":
                return "Image Generation is not fully configured!"

        return ""

from typing import Dict, Optional, Annotated
from sqlmodel import Field, Column, JSON
from .mutable_sa_base_model import MutableSABaseModel

class LLMConfig(MutableSABaseModel):
    model_name: str = Field(default="mistralai/Mistral-7B-Instruct-v0.3")
    hf_token: str
    prompt_preset: str

class AweTokenConfig(MutableSABaseModel):
    user_price: int = Field(default=100)
    max_token_per_tx: int = Field(default=0)
    max_token_per_round: int = Field(default=0)
    max_payment_per_round: int = Field(default=0)
    max_invocation_per_payment: int = Field(default=20)
    game_pool_division: Annotated[int, Field(default=70, ge=0, le=100)] = 70
    emission_creator_division: Annotated[int, Field(default=50, ge=0, le=100)] = 50

AweTokenConfigSAType = AweTokenConfig.to_sa_type()

class AweAgent(MutableSABaseModel):
    llm_config: Optional[LLMConfig] = Field(sa_column=Column(LLMConfig.to_sa_type()))
    image_generation_enabled: bool = Field(default=False)
    image_generation_args: Optional[Dict] = Field(sa_column=Column(JSON))
    awe_token_enabled: Annotated[bool, Field(default=True)] = True
    awe_token_config: Optional[AweTokenConfig] = Field(sa_column=Column(AweTokenConfig.to_sa_type()))

AweAgentSAType = AweAgent.to_sa_type()

from sqlmodel import SQLModel, Field
from typing import Annotated, Optional
from .utils import unix_timestamp_in_seconds


class TgUserAgentPayment(SQLModel, table=True):
    id: Annotated[Optional[int], Field(primary_key=True)]
    user_agent_id: Annotated[int, Field(index=True, nullable=False)]
    tg_user_id: Annotated[str, Field(index=True, nullable=False)]
    round: Annotated[int, Field(index=True, nullable=False)]
    amount: Annotated[int, Field(nullable=False)]
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)

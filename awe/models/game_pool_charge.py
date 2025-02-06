from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds
from typing import Annotated

class GamePoolCharge(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    approve_tx_hash: Annotated[str, Field(nullable=True)]
    tx_hash: Annotated[str, Field(nullable=True)]
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)

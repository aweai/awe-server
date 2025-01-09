from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds

class GamePoolCharge(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=False)
    amount: int = Field(nullable=False)
    tx_hash: str = Field(nullable=False)
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)

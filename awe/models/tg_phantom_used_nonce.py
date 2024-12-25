from sqlmodel import SQLModel, Field
from awe.models.utils import unix_timestamp_in_seconds

class TGPhantomUsedNonce(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    nonce: str = Field(unique=True)
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)

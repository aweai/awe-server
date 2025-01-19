from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds

class TGUserDMChat(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    user_agent_id: int = Field(index=True, nullable=False)
    tg_user_id: str = Field(index=True, nullable=False)
    chat_id: str = Field(index=False, nullable=False)
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)

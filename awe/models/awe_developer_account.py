from sqlmodel import SQLModel, Field
from typing import Annotated, Optional
from .utils import unix_timestamp_in_seconds

class AweDeveloperAccount(SQLModel, table=True):
    id: Annotated[Optional[int], Field(primary_key=True)]
    balance: Annotated[int, Field(default=0, nullable=False)] = 0
    created_at: int = Field(nullable=False, default_factory=unix_timestamp_in_seconds)

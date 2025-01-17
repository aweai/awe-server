from sqlmodel import SQLModel, Field
from typing import Annotated
from .utils import unix_timestamp_in_seconds

class PlayerWeeklyEmissions(SQLModel, table=True):
    id: Annotated[int, Field(primary_key=True, default=None)]
    user_agent_id: Annotated[int, Field(index=True, nullable=False)]
    tg_user_id: Annotated[str, Field(index=True, nullable=False)]
    day: Annotated[int, Field(index=True, nullable=False)]
    score: Annotated[int, Field(index=False, nullable=False, default=0)] = 0
    emission: Annotated[int, Field(index=False, nullable=False, default=0)] = 0
    created_at: Annotated[int, Field(nullable=False, default_factory=unix_timestamp_in_seconds)]

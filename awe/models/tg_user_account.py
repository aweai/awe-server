from sqlmodel import SQLModel, Field, Session, select
from typing import Annotated, Optional
from .utils import unix_timestamp_in_seconds
from awe.db import engine

class TgUserAccount(SQLModel, table=True):
    id: Annotated[Optional[int], Field(primary_key=True)]
    tg_user_id: Annotated[str, Field(unique=True, nullable=False)]
    balance: Annotated[int, Field(default=0, nullable=False)] = 0
    rewards: Annotated[int, Field(default=0, nullable=False)] = 0
    created_at: int = Field(index=True, nullable=False, default_factory=unix_timestamp_in_seconds)

    @classmethod
    def get_balance(cls, tg_user_id: str):
        with Session(engine) as session:
            statement = select(TgUserAccount).where(TgUserAccount.tg_user_id == tg_user_id)
            user_account = session.exec(statement).first()
            if user_account is None:
                return 0

            return user_account.balance

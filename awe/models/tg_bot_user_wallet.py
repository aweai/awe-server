from sqlmodel import SQLModel, Field
from sqlmodel import Session, select
from awe.db import engine
from typing_extensions import Self, Optional

class TGBotUserWallet(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    address: str = Field(nullable=True)
    phantom_session: str = Field(nullable=True)
    phantom_encryption_public_key: str = Field(nullable=True)

    @classmethod
    def get_user_wallet(cls, tg_user_id: str) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(TGBotUserWallet).where(TGBotUserWallet.tg_user_id == tg_user_id)
            return session.exec(statement).first()

from sqlmodel import SQLModel, Field
from sqlmodel import Session, select
from awe.db import engine

class TGBotUserWallet(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    address: str = Field(nullable=True)
    phantom_session: str = Field(nullable=True)
    phantom_encryption_public_key: str = Field(nullable=True)

    @classmethod
    def get_user_wallet_address(cls, user_agent_id: int, tg_user_id: str) -> str:
        with Session(engine) as session:
            statement = select(TGBotUserWallet).where(TGBotUserWallet.tg_user_id == tg_user_id, TGBotUserWallet.user_agent_id == user_agent_id)
            user_wallet = session.exec(statement).first()
            if user_wallet is None:
                return ""
            else:
                return user_wallet.address

    @classmethod
    def set_user_wallet_address(cls, user_agent_id: int, tg_user_id: str, wallet_address: str):
        with Session(engine) as session:
            statement = select(TGBotUserWallet).where(TGBotUserWallet.tg_user_id == tg_user_id, TGBotUserWallet.user_agent_id == user_agent_id)
            user_wallet = session.exec(statement).first()
            if user_wallet is None:
                user_wallet = TGBotUserWallet(tg_user_id=tg_user_id, user_agent_id=user_agent_id)

            user_wallet.address = wallet_address
            session.add(user_wallet)
            session.commit()

from typing import Optional
from typing_extensions import Self
from sqlmodel import SQLModel, Field
from sqlmodel import Session, select
from awe.db import engine

class UserAgentData(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    user_agent_id: int = Field(unique=True, nullable=False, foreign_key="useragent.id")

    # Agent state
    awe_token_round_transferred: int = Field(default=0)
    current_round: Optional[int] = Field(default=1, nullable=True)

    # Game pool
    awe_token_quote: int = Field(default=0)

    # Staking pool
    awe_token_staking: int = Field(default=0, nullable=True)

    # Statistics
    total_invocations: int = Field(default=0)
    total_users: int = Field(default=0)

    total_emissions: int = Field(default=0, nullable=True)
    total_income_shares: int = Field(default=0, nullable=True)

    awe_token_total_transferred: int = Field(default=0)
    awe_token_total_transactions: int = Field(default=0)
    awe_token_total_addresses: int = Field(default=0)

    @classmethod
    def get_user_agent_data_by_id(cls, user_agent_id: int) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(UserAgentData).where(UserAgentData.user_agent_id == user_agent_id)
            user_agent_data = session.exec(statement).first()
            return user_agent_data

    @classmethod
    def add_awe_token_quote(cls, user_agent_id: int, quote: int) -> Self:
        with Session(engine) as session:
            statement = select(UserAgentData).where(UserAgentData.user_agent_id == user_agent_id)
            user_agent_data = session.exec(statement).first()
            if user_agent_data is None:
                user_agent_data = UserAgentData(user_agent_id=user_agent_id, awe_token_quote=quote)
            else:
                user_agent_data.awe_token_quote = UserAgentData.awe_token_quote + quote

            session.add(user_agent_data)
            session.commit()

            session.refresh(user_agent_data)
            return user_agent_data

    @classmethod
    def add_user(cls, user_agent_id: int):
        with Session(engine) as session:
            statement = select(UserAgentData).where(
                UserAgentData.user_agent_id == user_agent_id
            )
            user_agent_data = session.exec(statement).first()

            if user_agent_data is None:
                user_agent_data = UserAgentData(user_agent_id=user_agent_id, total_users=1)
            else:
                user_agent_data.total_users = UserAgentData.total_users + 1

            session.add(user_agent_data)
            session.commit()

    @classmethod
    def add_invocation(cls, user_agent_id: int):
        with Session(engine) as session:
            statement = select(UserAgentData).where(
                UserAgentData.user_agent_id == user_agent_id
            )
            user_agent_data = session.exec(statement).first()

            if user_agent_data is None:
                user_agent_data = UserAgentData(user_agent_id=user_agent_id, total_invocations=1)
            else:
                user_agent_data.total_invocations = UserAgentData.total_invocations + 1

            session.add(user_agent_data)
            session.commit()

    @classmethod
    def add_awe_token_transfer_stats(cls, user_agent_id: int, amount: int, is_new_address: bool):
        with Session(engine) as session:
            statement = select(UserAgentData).where(
                UserAgentData.user_agent_id == user_agent_id
            )
            user_agent_data = session.exec(statement).first()

            if user_agent_data is None:
                user_agent_data = UserAgentData(
                    user_agent_id=user_agent_id,
                    awe_token_total_transactions=1,
                    awe_token_total_transferred=amount,
                    awe_token_total_addresses=1
                )
            else:
                user_agent_data.awe_token_total_transactions = UserAgentData.awe_token_total_transactions + 1
                user_agent_data.awe_token_total_transferred = UserAgentData.awe_token_total_transferred + amount

                if is_new_address:
                    user_agent_data.awe_token_total_addresses = UserAgentData.awe_token_total_addresses + 1

            session.add(user_agent_data)
            session.commit()

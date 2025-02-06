from typing import Optional, Annotated
from typing_extensions import Self
from sqlmodel import SQLModel, Field
from sqlmodel import Session, select
from awe.db import engine

class UserAgentData(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    user_agent_id: int = Field(unique=True, nullable=False, foreign_key="useragent.id")

    # Agent state
    awe_token_round_transferred: Annotated[int, Field(default=0)] = 0
    current_round: Annotated[int, Field(default=1)] = 1
    current_round_started_at: Annotated[int, Field(default=0)] = 0

    # Game pool
    awe_token_quote: Annotated[int, Field(default=0)] = 0

    # Staking pool
    awe_token_staking: Annotated[int, Field(default=0)] = 0

    # Statistics
    total_invocations: Annotated[int, Field(default=0)] = 0
    total_users: Annotated[int, Field(default=0)] = 0

    total_emissions: Annotated[int, Field(default=0)] = 0
    total_income_shares: Annotated[int, Field(default=0)] = 0

    awe_token_total_transferred: Annotated[int, Field(default=0)] = 0
    awe_token_total_transactions: Annotated[int, Field(default=0)] = 0
    awe_token_total_addresses: Annotated[int, Field(default=0)] = 0

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

            user_agent_data.awe_token_total_transactions = UserAgentData.awe_token_total_transactions + 1
            user_agent_data.awe_token_total_transferred = UserAgentData.awe_token_total_transferred + amount

            if is_new_address:
                user_agent_data.awe_token_total_addresses = UserAgentData.awe_token_total_addresses + 1

            session.add(user_agent_data)
            session.commit()

    @classmethod
    def add_income_shares(cls, user_agent_id: int, amount: int, session: Session):
        statement = select(UserAgentData).where(
            UserAgentData.user_agent_id == user_agent_id
        )
        user_agent_data = session.exec(statement).first()
        user_agent_data.total_income_shares = UserAgentData.total_income_shares + amount
        session.add(user_agent_data)

    @classmethod
    def add_staking(cls, user_agent_id: int, amount: int, session: Session):
        statement = select(UserAgentData).where(
            UserAgentData.user_agent_id == user_agent_id
        )
        user_agent_data = session.exec(statement).first()
        user_agent_data.awe_token_staking = UserAgentData.awe_token_staking + amount
        session.add(user_agent_data)

    @classmethod
    def release_staking(cls, user_agent_id: int, amount: int):
        with Session(engine) as session:
            statement = select(UserAgentData).where(
                UserAgentData.user_agent_id == user_agent_id
            )
            user_agent_data = session.exec(statement).first()

            user_agent_data.awe_token_staking = UserAgentData.awe_token_staking - amount

            session.add(user_agent_data)
            session.commit()

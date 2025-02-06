
from sqlmodel import SQLModel, Field, Session, select
from awe.db import engine
from typing import Optional, Annotated
from typing_extensions import Self
from . import UserAgentData

class UserAgentUserInvocations(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    tg_user_id: str = Field(index=True, nullable=False)
    user_agent_id: int = Field(index=True, nullable=False)
    current_round: int = Field(default=0, nullable=False)
    round_payments: Annotated[int, Field(default=1, nullable=False)] = 1
    payment_invocations: int = Field(default=0, nullable=False)

    @classmethod
    def get_user_invocation(cls, user_agent_id: int, tg_user_id: str) -> Optional[Self]:
        with Session(engine) as session:
            statement = select(UserAgentUserInvocations).where(
                UserAgentUserInvocations.user_agent_id == user_agent_id,
                UserAgentUserInvocations.tg_user_id == tg_user_id
            )
            return session.exec(statement).first()


    @classmethod
    def add_invocation(cls, user_agent_id: int, tg_user_id: str):
        with Session(engine) as session:
            statement = select(UserAgentUserInvocations).where(
                UserAgentUserInvocations.user_agent_id == user_agent_id,
                UserAgentUserInvocations.tg_user_id == tg_user_id
            )
            user_invoke = session.exec(statement).first()
            user_invoke.payment_invocations = UserAgentUserInvocations.payment_invocations + 1

            session.add(user_invoke)
            session.commit()

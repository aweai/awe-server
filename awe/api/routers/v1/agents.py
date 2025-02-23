from fastapi import APIRouter, Query
from typing import List, Annotated, Literal
from awe.db import engine
from sqlmodel import Session, select
from awe.models import UserAgent
from sqlalchemy import func
from sqlalchemy.orm import load_only, joinedload
from pydantic import BaseModel


router = APIRouter(
    prefix="/v1/agents"
)

page_size = 20

class AgentListItem(BaseModel):
    id: int
    name: str
    tg_username: str
    description: str

    pool: int
    staking: int

    invocations: int
    score: int


@router.get("", response_model=List[AgentListItem])
def get_agent_list(
    list: Literal["leaderboard", "discover"] = "leaderboard",
    page: Annotated[int, Query(ge=0)] = 0
):
    if page < 0:
        page = 0

    with Session(engine) as session:
        statement = select(UserAgent)
        if list == "leaderboard":
            statement = statement.order_by(UserAgent.score.desc()).offset(page * page_size)
        else:
            statement = statement.order_by(func.random())

        statement = statement.options(
            joinedload(UserAgent.agent_data),
            load_only(
                UserAgent.id,
                UserAgent.name,
                UserAgent.score,
                UserAgent.tg_bot
            )
        ).where(
            UserAgent.enabled == True
        ).limit(page_size)

        user_agents = session.exec(statement).all()

        agent_list_items = [
            AgentListItem(
                id=user_agent.id,
                name=user_agent.name,
                score=user_agent.score,
                tg_username=user_agent.tg_bot.username,
                description=user_agent.tg_bot.start_message,
                invocations=user_agent.agent_data.total_invocations,
                pool=user_agent.agent_data.awe_token_quote,
                staking=user_agent.agent_data.awe_token_staking
            )
            for user_agent in user_agents
        ]

        return agent_list_items

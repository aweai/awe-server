from fastapi import APIRouter, Depends
from typing import Optional, Annotated, List
from awe.api.dependencies import validate_user_agent
from sqlmodel import SQLModel, Session, select
from awe.models.utils import get_day_as_timestamp
from awe.models import UserAgentStatsStakingDailyCounts, UserAgentStatsInvocationDailyCounts, UserAgentStatsUserDailyCounts, UserAgentStatsTokenTransferDailyCounts, UserAgentStatsPaymentDailyCounts
from awe.db import engine

router = APIRouter(
    prefix="/v1/agent-stats"
)

days_to_fetch = 14

class StatsInvocationsResponse(SQLModel):
    days: List[int] = []
    users: List[int] = []
    llm: List[int] = []
    sd: List[int] = []
    token_query: List[int] = []
    token_transfer: List[int] = []

@router.get("/{agent_id}/invocations", response_model=Optional[StatsInvocationsResponse])
def get_invocations_by_agent_id(agent_id, _: Annotated[bool, Depends(validate_user_agent)]):
    start_day = get_day_as_timestamp() - days_to_fetch * 86400

    with Session(engine) as session:
        invocation_statement = select(UserAgentStatsInvocationDailyCounts).where(
            UserAgentStatsInvocationDailyCounts.user_agent_id == agent_id,
            UserAgentStatsInvocationDailyCounts.day >= start_day
        )

        invocation_stats = session.exec(invocation_statement).all()

        user_statement = select(UserAgentStatsUserDailyCounts).where(
            UserAgentStatsUserDailyCounts.user_agent_id == agent_id,
            UserAgentStatsUserDailyCounts.day >= start_day
        )

        user_stats = session.exec(user_statement).all()

    response = StatsInvocationsResponse()

    stats_dict = {}

    for day in range(start_day, start_day + (days_to_fetch + 1) * 86400, 86400):
        response.days.append(day)
        stats_dict[day] = {
            'llm': 0,
            'sd': 0,
            'token_query': 0,
            'token_transfer': 0,
            'users': 0
        }

    for stat in invocation_stats:
        stats_dict[stat.day][stat.tool.lower()] = stat.invocations

    for stat in user_stats:
        stats_dict[stat.day]['users'] = stat.users

    for day in response.days:
        response.llm.append(stats_dict[day]['llm'])
        response.sd.append(stats_dict[day]['sd'])
        response.token_query.append(stats_dict[day]['token_query'])
        response.token_transfer.append(stats_dict[day]['token_transfer'])
        response.users.append(stats_dict[day]['users'])

    return response

class StatsTokenTransfersResponse(SQLModel):
    days: List[int] = []
    transactions: List[int] = []
    amounts: List[int] = []
    addresses: List[int] = []

@router.get("/{agent_id}/token-transfers", response_model=Optional[StatsTokenTransfersResponse])
def get_token_transfers_by_agent_id(agent_id, _: Annotated[bool, Depends(validate_user_agent)]):
    start_day = get_day_as_timestamp() - days_to_fetch * 86400

    with Session(engine) as session:
        token_statement = select(UserAgentStatsTokenTransferDailyCounts).where(
            UserAgentStatsTokenTransferDailyCounts.user_agent_id == agent_id,
            UserAgentStatsTokenTransferDailyCounts.day >= start_day
        )

        token_stats = session.exec(token_statement).all()

    response = StatsTokenTransfersResponse()

    stats_dict = {}

    for day in range(start_day, start_day + (days_to_fetch + 1) * 86400, 86400):
        response.days.append(day)
        stats_dict[day] = {
            'transactions': 0,
            'amounts': 0,
            'addresses': 0
        }

    for stat in token_stats:
        stats_dict[stat.day]['transactions'] = stat.transactions
        stats_dict[stat.day]['amounts'] = stat.amount
        stats_dict[stat.day]['addresses'] = stat.addresses

    for day in response.days:
        response.transactions.append(stats_dict[day]['transactions'])
        response.addresses.append(stats_dict[day]['addresses'])
        response.amounts.append(stats_dict[day]['amounts'])

    return response


class StatsUserPaymentResponse(SQLModel):
    days: List[int] = []
    transactions: List[int] = []
    pool_amounts: List[int] = []
    creator_amounts: List[int] = []
    addresses: List[int] = []

@router.get("/{agent_id}/user-payments", response_model=Optional[StatsUserPaymentResponse])
def get_user_payments_by_agent_id(agent_id, _: Annotated[bool, Depends(validate_user_agent)]):
    start_day = get_day_as_timestamp() - days_to_fetch * 86400

    with Session(engine) as session:
        token_statement = select(UserAgentStatsPaymentDailyCounts).where(
            UserAgentStatsPaymentDailyCounts.user_agent_id == agent_id,
            UserAgentStatsPaymentDailyCounts.day >= start_day
        )

        token_stats = session.exec(token_statement).all()

    response = StatsUserPaymentResponse()

    stats_dict = {}

    for day in range(start_day, start_day + (days_to_fetch + 1) * 86400, 86400):
        response.days.append(day)
        stats_dict[day] = {
            'transactions': 0,
            'pool_amounts': 0,
            'creator_amounts': 0,
            'addresses': 0
        }

    for stat in token_stats:
        stats_dict[stat.day]['transactions'] = stat.transactions
        stats_dict[stat.day]['pool_amounts'] = stat.pool_amount
        stats_dict[stat.day]['creator_amounts'] = stat.creator_amount
        stats_dict[stat.day]['addresses'] = stat.addresses

    for day in response.days:
        response.transactions.append(stats_dict[day]['transactions'])
        response.addresses.append(stats_dict[day]['addresses'])
        response.pool_amounts.append(stats_dict[day]['pool_amounts'])
        response.creator_amounts.append(stats_dict[day]['creator_amounts'])

    return response


class StatsUserStakingResponse(SQLModel):
    days: List[int] = []
    in_amounts: List[int] = []
    out_amounts: List[int] = []


@router.get("/{agent_id}/user-staking", response_model=Optional[StatsUserStakingResponse])
def get_user_staking_by_agent_id(agent_id, _: Annotated[bool, Depends(validate_user_agent)]):
    start_day = get_day_as_timestamp() - days_to_fetch * 86400

    with Session(engine) as session:
        token_statement = select(UserAgentStatsStakingDailyCounts).where(
            UserAgentStatsStakingDailyCounts.user_agent_id == agent_id,
            UserAgentStatsStakingDailyCounts.day >= start_day
        )

        token_stats = session.exec(token_statement).all()

    response = StatsUserStakingResponse()

    stats_dict = {}

    for day in range(start_day, start_day + (days_to_fetch + 1) * 86400, 86400):
        response.days.append(day)
        stats_dict[day] = {
            'in_amounts': 0,
            'out_amounts': 0,
        }

    for stat in token_stats:
        stats_dict[stat.day]['in_amounts'] = stat.in_amount
        stats_dict[stat.day]['out_amounts'] = stat.out_amount

    for day in response.days:
        response.in_amounts.append(stats_dict[day]['in_amounts'])
        response.out_amounts.append(stats_dict[day]['out_amounts'])

    return response

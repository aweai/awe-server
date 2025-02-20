from fastapi import APIRouter, Depends, BackgroundTasks, Query
from typing import Optional, Annotated, List
from pydantic import BaseModel
from awe.models import UserAgentData, UserAgentWeeklyEmissions, PlayerWeeklyEmissions, StakerWeeklyEmissions, AweDeveloperAccount
from awe.api.dependencies import get_admin
from awe.blockchain import awe_on_chain
from awe.models.utils import get_day_as_timestamp
from awe.settings import settings
from awe.agent_manager.agent_score import update_all_agent_scores
from awe.agent_manager.agent_emissions import distribute_all_agent_emissions
from awe.agent_manager.in_agent_emissions import distribute_all_in_agent_emissions
import logging
import traceback
from awe.db import engine
from sqlmodel import Session, select
from awe.maintenance import start_maintenance, stop_maintenance, is_in_maintenance_sync

logger = logging.getLogger("[Admin API]")

router = APIRouter(
    prefix="/v1/admin"
)


@router.get("/system/wallet")
def get_system_wallet(_: Annotated[str, Depends(get_admin)]):
    system_public_key = awe_on_chain.get_system_payer()
    system_balance = awe_on_chain.get_balance(system_public_key)
    return {
        "address": system_public_key,
        "balance": awe_on_chain.token_ui_amount(system_balance)
    }


@router.get("/system/developer/account")
def get_developer_account(_: Annotated[str, Depends(get_admin)]):
    with Session(engine) as session:
        statement = select(AweDeveloperAccount)
        account = session.exec(statement).first()
        if account is None:
            return 0
        return account.balance


@router.get("/agents/{agent_id}/data", response_model=Optional[UserAgentData])
def get_user_agent_data(agent_id, _: Annotated[str, Depends(get_admin)]):
    user_agent_data = UserAgentData.get_user_agent_data_by_id(agent_id)
    return user_agent_data


class QuoteParams(BaseModel):
    amount: int

@router.post("/agents/{agent_id}/awe_quote", response_model=Optional[UserAgentData])
def add_user_agent_awe_quote(agent_id, quote_params: QuoteParams, _: Annotated[str, Depends(get_admin)]):
    user_agent_data = UserAgentData.add_awe_token_quote(agent_id, quote_params.amount)
    return user_agent_data


@router.post("/system/agent-emissions")
def update_agent_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_agent_emissions_task, last_cycle_end, dry_run == 1)
    return "Task initiated!"


@router.get("/system/agent-emissions", response_model=List[UserAgentWeeklyEmissions])
def get_agent_emissions(_: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0, page: Optional[int] = 0):

    page_size = 100

    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    last_cycle_start = last_cycle_end - settings.tn_emission_interval_days * 86400

    with Session(engine) as session:
        statement = select(UserAgentWeeklyEmissions).where(
            UserAgentWeeklyEmissions.day == last_cycle_start
        ).order_by(UserAgentWeeklyEmissions.score.desc()).offset(page * page_size).limit(page_size)

        agent_emissions = session.exec(statement).all()

        return agent_emissions


@router.get("/system/agent-emissions/{agent_id}/players", response_model=List[PlayerWeeklyEmissions])
def get_agent_player_emissions(agent_id: int, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0, page: Optional[int] = 0):
    page_size = 100

    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    last_cycle_start = last_cycle_end - settings.tn_emission_interval_days * 86400

    with Session(engine) as session:
        statement = select(PlayerWeeklyEmissions).where(
            PlayerWeeklyEmissions.user_agent_id == agent_id,
            PlayerWeeklyEmissions.day == last_cycle_start
        ).order_by(PlayerWeeklyEmissions.score.desc()).offset(page * page_size).limit(page_size)

        player_emissions = session.exec(statement).all()

        return player_emissions


@router.get("/system/agent-emissions/{agent_id}/stakers", response_model=List[StakerWeeklyEmissions])
def get_agent_staker_emissions(agent_id: int, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0, page: Optional[int] = 0):
    page_size = 100

    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    last_cycle_start = last_cycle_end - settings.tn_emission_interval_days * 86400

    with Session(engine) as session:
        statement = select(StakerWeeklyEmissions).where(
            StakerWeeklyEmissions.user_agent_id == agent_id,
            StakerWeeklyEmissions.day == last_cycle_start
        ).order_by(StakerWeeklyEmissions.score.desc()).offset(page * page_size).limit(page_size)

        staker_emissions = session.exec(statement).all()

        return staker_emissions


@router.post("/system/maintenance")
def start_maintenance_mode(_: Annotated[str, Depends(get_admin)]) -> bool:
    start_maintenance()
    return is_in_maintenance_sync()


@router.delete("/system/maintenance")
def stop_maintenance_mode(_: Annotated[str, Depends(get_admin)]) -> bool:
    stop_maintenance()
    return is_in_maintenance_sync()


def get_last_emission_cycle_end_before(before_timestamp: int) -> int:
    if before_timestamp == 0:
        # Update for the last cycle
        before_timestamp = get_day_as_timestamp()

    interval_seconds = settings.tn_emission_interval_days * 86400

    # Calculate the end timestamp of last cycle
    emission_start = settings.tn_emission_start

    if before_timestamp <= emission_start:
        raise Exception("Invalid for_cycle_before provided")

    elapsed_time  = before_timestamp - emission_start
    completed_cycles = elapsed_time // interval_seconds

    return emission_start + (completed_cycles * interval_seconds)


def update_agent_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        update_all_agent_scores(last_cycle_end, dry_run)

        if not dry_run:
            distribute_all_agent_emissions(last_cycle_end)
            distribute_all_in_agent_emissions(last_cycle_end)

    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())

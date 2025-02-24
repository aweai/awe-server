from fastapi import APIRouter, Depends, BackgroundTasks, Query
from awe.models.utils import get_day_as_timestamp
from awe.settings import settings
from awe.agent_manager.agent_score import update_all_agent_scores
from awe.agent_manager.agent_emissions import distribute_top_agent_emissions, update_total_cycle_emissions, distribute_global_staking_emissions, update_all_emission_account_balances, distribute_new_agent_emissions
from awe.agent_manager.in_agent_emissions import distribute_all_in_agent_emissions
import logging
import traceback
from awe.models import UserAgentWeeklyEmissions, PlayerWeeklyEmissions, StakerWeeklyEmissions
from typing import Optional, Annotated, List
from awe.api.dependencies import get_admin
from awe.db import engine
from sqlmodel import Session, select


logger = logging.getLogger("[Emission API]")

router = APIRouter(
    prefix="/v1/emissions"
)


@router.post("/emissions/cycle")
def update_cycle_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_total_cycle_emissions_task, last_cycle_end, dry_run == 1)
    return "Update agent scores task initiated!"


@router.post("/agents/scores")
def update_agent_scores(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_agent_scores_task, last_cycle_end, dry_run == 1)
    return "Update agent scores task initiated!"


@router.post("/staking/emissions")
def update_global_staking_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_global_staking_emissions_task, last_cycle_end, dry_run == 1)
    return "Update global staking emissions task initiated!"


@router.post("/agents/top/emissions")
def update_top_agent_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_top_agent_emissions_task, last_cycle_end, dry_run == 1)
    return "Update top agent emissions task initiated!"


@router.post("/agents/new/emissions")
def update_new_agent_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_new_agent_emissions_task, last_cycle_end, dry_run == 1)
    return "Update new agent emissions task initiated!"


@router.post("/in-agents/emissions")
def update_in_agent_emissions(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_in_agent_emissions_task, last_cycle_end, dry_run == 1)
    return "Update in-agent emissions task initiated!"

@router.post("/emissions/balance")
def update_emission_balances(dry_run: Annotated[int, Query(ge=0, le=1)], background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):
    last_cycle_end = get_last_emission_cycle_end_before(last_cycle_before)
    background_tasks.add_task(update_in_agent_emissions_task, last_cycle_end, dry_run == 1)
    return "Update in-agent emissions task initiated!"

@router.get("/agents/emissions", response_model=List[UserAgentWeeklyEmissions])
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


def update_total_cycle_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        update_total_cycle_emissions(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_agent_scores_task(last_cycle_end: int, dry_run: bool):
    try:
        update_all_agent_scores(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_global_staking_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        distribute_global_staking_emissions(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_top_agent_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        distribute_top_agent_emissions(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_new_agent_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        distribute_new_agent_emissions(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_in_agent_emissions_task(last_cycle_end: int, dry_run: bool):
    try:
        distribute_all_in_agent_emissions(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


def update_emission_balances_task(last_cycle_end: int, dry_run: bool):
    try:
        update_all_emission_account_balances(last_cycle_end, dry_run)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())

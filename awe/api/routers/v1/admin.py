from fastapi import APIRouter, Depends, BackgroundTasks
from typing import Optional, Annotated
from pydantic import BaseModel
from awe.models.user_agent_data import UserAgentData
from awe.api.dependencies import get_admin
from awe.blockchain import awe_on_chain
from awe.models.utils import get_day_as_timestamp
from awe.settings import settings
from awe.agent_manager.agent_score import update_all_agent_scores
from awe.agent_manager.agent_emissions import update_all_agent_emissions
from awe.agent_manager.player_emissions import update_player_emissions, update_staker_emissions
import logging
import traceback

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
def update_agent_emissions(background_tasks: BackgroundTasks, _: Annotated[str, Depends(get_admin)], last_cycle_before: Optional[int] = 0):

    if last_cycle_before == 0:
        # Update for the last cycle
        last_cycle_before = get_day_as_timestamp()

    interval_seconds = settings.tn_emission_interval_days * 86400

    # Calculate the end timestamp of last cycle
    emission_start = settings.tn_emission_start

    if last_cycle_before <= emission_start:
        raise Exception("Invalid for_cycle_before provided")

    elapsed_time  = last_cycle_before - emission_start
    completed_cycles = elapsed_time // interval_seconds

    last_cycle_end = emission_start + (completed_cycles * interval_seconds)

    background_tasks.add_task(update_agent_emissions, last_cycle_end)

    return "Task initiated!"

def update_agent_emissions(last_cycle_end: int):
    try:
        update_all_agent_scores(last_cycle_end)
        update_all_agent_emissions(last_cycle_end)
        update_player_emissions(last_cycle_end)
        # update_staker_emissions(last_cycle_end)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())

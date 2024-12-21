from fastapi import APIRouter, Depends
from typing import Optional, Annotated
from pydantic import BaseModel
from awe.models.user_agent_data import UserAgentData
from awe.api.dependencies import get_admin
from awe.blockchain import awe_on_chain

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

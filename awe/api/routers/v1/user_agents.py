from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks, Query
from awe.models.user_agent import UserAgent
from awe.models.user_agent_data import UserAgentData
from awe.models.tg_bot import TGBot
from awe.models.awe_agent import AweAgent, LLMConfig
from awe.db import engine
from sqlmodel import Session, select, func, col, SQLModel
from ...dependencies import get_current_user, validate_user_agent
from awe.blockchain import awe_on_chain
from sqlalchemy.orm import load_only, joinedload
from sd_task.task_args.inference_task.task_args import InferenceTaskArgs
from PIL import Image
from awe.models.utils import unix_timestamp_in_seconds
from awe.settings import settings
import logging
import re
from awe.maintenance import is_in_maintenance_sync
from awe.agent_manager.agent_fund import collect_game_pool_charge, refund_agent_staking, withdraw_to_creator, collect_agent_creation_staking
import traceback


logger = logging.getLogger("[User Agents API]")

router = APIRouter(
    prefix="/v1/user-agents"
)

class AgentListTGBot(SQLModel):
    username: str

class AgentListResponse(SQLModel):
    id: int
    name: str
    enabled: bool
    tg_bot: Optional[AgentListTGBot]
    agent_data: Optional[UserAgentData]


def get_local_user_agents(user_address: str) -> list[AgentListResponse]:
    with Session(engine) as session:
        statement = select(
            UserAgent
        ).options(
            joinedload(UserAgent.agent_data),
            load_only(
                UserAgent.id,
                UserAgent.name,
                UserAgent.enabled,
                UserAgent.tg_bot
            )
        ).where(
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        ).order_by(
            UserAgent.created_at.desc()
        )

        user_agents = session.exec(statement).all()

        return user_agents


@router.put("/{agent_id}", response_model=Optional[UserAgent])
def update_user_agent(agent_id, user_agent: UserAgent, user_address: Annotated[str, Depends(get_current_user)]):
    with Session(engine) as session:
        statement = select(UserAgent).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        user_agent_in_db = session.exec(statement).first()
        if user_agent_in_db is None:
            return None

    try:
        # A SQLModel bug
        # https://github.com/fastapi/sqlmodel/discussions/961
        if user_agent.tg_bot is not None:
            user_agent.tg_bot = TGBot.model_validate(user_agent.tg_bot)
        if user_agent.awe_agent is not None:
            user_agent.awe_agent = AweAgent.model_validate(user_agent.awe_agent)

        # Token must be enabled for now
        user_agent.awe_agent.awe_token_enabled = True

        # Validate agent prompt
        if re.search("\{|\}", user_agent.awe_agent.llm_config.prompt_preset) is not None:
            raise Exception("Invalid LLM prompt")

        # Validate ImageGenrationArgs manually
        # since we can not use the Pydantic model of ImageGenrationArgs here inside SQLModel
        if user_agent.awe_agent is None or user_agent.awe_agent.image_generation_args is None:
            raise Exception("Invalid input")

        prompt_placeholder_inserted = False
        base_model_placeholder_inserted = False

        if 'prompt' not in user_agent.awe_agent.image_generation_args or user_agent.awe_agent.image_generation_args["prompt"] == "":
            user_agent.awe_agent.image_generation_args["prompt"] = "placeholder"
            prompt_placeholder_inserted = True

        if 'base_model' not in user_agent.awe_agent.image_generation_args:
            user_agent.awe_agent.image_generation_args["base_model"] = {}

        if "name" not in user_agent.awe_agent.image_generation_args["base_model"] or user_agent.awe_agent.image_generation_args["base_model"]["name"] == "":
            user_agent.awe_agent.image_generation_args["base_model"]["name"] = "placeholder"
            base_model_placeholder_inserted = True

        # Remove empty LoRA dict for args validation
        if "lora" in user_agent.awe_agent.image_generation_args:
            if "model" not in user_agent.awe_agent.image_generation_args["lora"] or user_agent.awe_agent.image_generation_args["lora"]["model"] == "":
                del user_agent.awe_agent.image_generation_args["lora"]

        image_generation_args_obj = InferenceTaskArgs.model_validate(user_agent.awe_agent.image_generation_args)
        user_agent.awe_agent.image_generation_args = image_generation_args_obj.model_dump()

        if prompt_placeholder_inserted:
            user_agent.awe_agent.image_generation_args["prompt"] = ""

        if base_model_placeholder_inserted:
            user_agent.awe_agent.image_generation_args["base_model"]["name"] = ""

        # Fix LLM Config
        if user_agent.awe_agent.llm_config is None:
            user_agent.awe_agent.llm_config = LLMConfig()

        user_agent.awe_agent.llm_config.hf_token = ""
        user_agent.awe_agent.llm_config.model_name = "mistralai/Mistral-7B-Instruct-v0.3"

        # Fix SD Config
        user_agent.awe_agent.image_generation_args["task_config"]["num_images"] = 1

        if user_agent.enabled:
            err_msg = user_agent.validate_for_enable()
        else:
            err_msg = user_agent.validate_for_save()

        if err_msg != "":
            raise Exception(err_msg)

    except Exception as e:
        logger.debug(str(e))
        raise HTTPException(status_code=400, detail=str(e))

    with Session(engine) as session:

        user_agent_in_db.name = user_agent.name
        user_agent_in_db.tg_bot = user_agent.tg_bot
        user_agent_in_db.awe_agent = user_agent.awe_agent
        user_agent_in_db.enabled = user_agent.enabled
        user_agent_in_db.updated_at = unix_timestamp_in_seconds()

        session.add(user_agent_in_db)

        if user_agent.enabled:
            agent_data = user_agent_in_db.agent_data
            if agent_data.current_round_started_at == 0:
                agent_data.current_round_started_at = unix_timestamp_in_seconds()
                session.add(agent_data)

        session.commit()
        session.refresh(user_agent_in_db)

    return user_agent_in_db


@router.get("/{agent_id}", response_model=Optional[UserAgent])
def get_user_agent_by_id(agent_id, user_address: Annotated[str, Depends(get_current_user)]):
    with Session(engine) as session:
        statement = select(UserAgent).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        user_agent = session.exec(statement).first()
        return user_agent


@router.get("", response_model=list[AgentListResponse])
def get_user_agents(user_address: Annotated[str, Depends(get_current_user)]):
    return get_local_user_agents(user_address)


@router.post("")
def create_user_agent(tx: str, background_tasks: BackgroundTasks, user_address: Annotated[str, Depends(get_current_user)]):
    if is_in_maintenance_sync():
        raise HTTPException(500, "System in maintenance. Please try again later.")

    background_tasks.add_task(wrap_collect_agent_creation_staking, user_address, tx)


def wrap_collect_agent_creation_staking(creator_address: str, approve_tx: str):
    try:
        collect_agent_creation_staking(creator_address, approve_tx)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


@router.get("/{agent_id}/data", response_model=Optional[UserAgentData])
def get_user_agent_data(agent_id, user_address: Annotated[str, Depends(get_current_user)]):

    agent_id = int(agent_id)

    with Session(engine) as session:
        statement = select(func.count(col(UserAgent.id))).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        num_agents_in_db = session.exec(statement).one()
        if num_agents_in_db == 0:
            return None

        statement = select(UserAgentData).where(UserAgentData.user_agent_id == agent_id)
        agent_data = session.exec(statement).first()

        if agent_data is None:
            agent_data = UserAgentData(user_agent_id=agent_id)

        return agent_data


@router.delete("/{agent_id}")
def delete_user_agent(agent_id, background_tasks: BackgroundTasks, user_address: Annotated[str, Depends(get_current_user)]):

    if is_in_maintenance_sync():
        raise HTTPException(500, "System in maintenance. Please try again later.")

    with Session(engine) as session:
        statement = select(UserAgent).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        user_agent = session.exec(statement).first()
        if user_agent is None:
            return None

        current_time = unix_timestamp_in_seconds()

        if current_time - user_agent.created_at < settings.tn_agent_staking_locking_days * 86400:
            raise Exception("Still in locking period, can not terminate")

        user_agent.updated_at = current_time
        user_agent.deleted_at = current_time
        user_agent.enabled = False
        session.add(user_agent)
        session.commit()
        session.refresh(user_agent)

        #TODO: Rlease all the player stakings on the Memegent

        background_tasks.add_task(wrap_refund_agent_staking, user_agent.id, user_agent.user_address, user_agent.staking_amount)


def wrap_refund_agent_staking(agent_id, creator_address, amount):
    try:
        refund_agent_staking(agent_id, creator_address, amount)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


@router.post("/{agent_id}/round", response_model=UserAgentData)
def start_new_round(agent_id, user_address: Annotated[str, Depends(get_current_user)]):
    with Session(engine) as session:
        statement = select(func.count(col(UserAgent.id))).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        num_agents_in_db = session.exec(statement).one()
        if num_agents_in_db == 0:
            return None

        statement = select(UserAgentData).where(UserAgentData.user_agent_id == agent_id)
        agent_data = session.exec(statement).first()

        agent_data.awe_token_round_transferred = 0
        agent_data.current_round = UserAgentData.current_round + 1
        agent_data.current_round_started_at = unix_timestamp_in_seconds()

        session.add(agent_data)
        session.commit()
        session.refresh(agent_data)

        return agent_data


@router.post("/{agent_id}/pfp")
def upload_pfp(agent_id, file: UploadFile, _: Annotated[bool, Depends(validate_user_agent)]):

    try:
        img = Image.open(file.file)
    except:
        raise HTTPException(status_code=401, detail="Invalid image uploaded!")

    keep_size = 256
    width, height = img.size
    new_edge_length = min(width, height)

    left = (width - new_edge_length) / 2
    top = (height - new_edge_length) / 2
    right = (width + new_edge_length) / 2
    bottom = (height + new_edge_length) / 2

    img_cropped = img.crop((left, top, right, bottom))
    img_resized = img_cropped.resize((keep_size, keep_size), Image.Resampling.LANCZOS)
    img_resized.save(f"persisted_data/pfps/{agent_id}.png", "PNG")


@router.post("/{agent_id}/game-pool")
def charge_game_pool(agent_id: int, amount: Annotated[int, Query(ge=settings.min_game_pool_charge_amount)], tx: str, background_tasks: BackgroundTasks, user_address: Annotated[str, Depends(get_current_user)]):
    if is_in_maintenance_sync():
        raise HTTPException(500, "System in maintenance. Please try again later")

    with Session(engine) as session:
        statement = select(UserAgent).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        user_agent = session.exec(statement).first()
        if user_agent is None:
            raise HTTPException(400, "Agent not found")

    background_tasks.add_task(wrap_collect_game_pool_charge, agent_id, user_address, amount, tx)


def wrap_collect_game_pool_charge(agent_id, user_address, amount, tx):
    try:
        collect_game_pool_charge(agent_id, user_address, amount, tx)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())


@router.post("/{agent_id}/account")
def withdraw_agent_account(agent_id: int, amount: Annotated[int, Query(ge=settings.min_creator_withdraw_amount)], background_tasks: BackgroundTasks, user_address: Annotated[str, Depends(get_current_user)]):
    if is_in_maintenance_sync():
        raise HTTPException(500, "System in maintenance. Please try again later")

    with Session(engine) as session:
        statement = select(UserAgent).options(joinedload(UserAgent.agent_data)).where(
            UserAgent.id == agent_id,
            UserAgent.user_address == user_address,
            UserAgent.deleted_at.is_(None)
        )
        user_agent = session.exec(statement).first()
        if user_agent is None:
            raise HTTPException(400, "Agent not found")

        if amount + settings.withdraw_tx_fee > user_agent.agent_data.awe_token_creator_balance:
            raise HTTPException(400, "Not enough balance")

    background_tasks.add_task(wrap_withdraw_to_creator, agent_id, amount)


def wrap_withdraw_to_creator(agent_id, amount):
    try:
        withdraw_to_creator(agent_id, amount)
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc())

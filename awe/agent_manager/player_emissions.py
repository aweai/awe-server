from sqlmodel import Session, select
from awe.db import engine
from awe.models import UserAgentWeeklyEmissions
from awe.settings import settings
import logging

logger = logging.getLogger("[Player Emissions]")

page_size = 500

def update_player_emissions(cycle_end_timestamp: int):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    # Get the list of agent with emissions
    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(UserAgentWeeklyEmissions).where(
                UserAgentWeeklyEmissions.emission != 0,
                UserAgentWeeklyEmissions.day == cycle_start_timestamp
            ).order_by(UserAgentWeeklyEmissions.id.asc()).offset(current_page * page_size).limit(page_size)

            agent_emissions = session.exec(statement).all()
            logger.info(f"{len(agent_emissions)} agents with emissions in page {current_page}")

            for agent_emission in agent_emissions:
                update_player_emissions_for_agent(agent_emission.user_agent_id, cycle_end_timestamp, agent_emission.emission)

            if len(agent_emissions) < page_size:
                break

            current_page += 1

    logger.info("All players emissions updated!")



def update_player_emissions_for_agent(agent_id: int, cycle_end_timestamp: int, agent_emissions: int):
    pass


def update_staker_emissions(cycle_end_timestamp: int):
    pass


def update_staker_emissions_for_agent(agent_id: int, cycle_end_timestamp: int):
    pass

from awe.db import engine
from sqlmodel import Session, select, or_
from awe.settings import settings
from datetime import datetime
import logging
from awe.models import UserAgent, UserAgentWeeklyEmissions
from sqlalchemy import func
import math

logger = logging.getLogger("[Agent Emissions]")

page_size = 500

def distribute_all_agent_emissions(cycle_end_timestamp: int):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.info(f"Updating agent emissions for cycle: [{start_datetime}, {end_datetime})")

    # Calculate the number of top Memegents
    with Session(engine) as session:
        statement = select(func.count(UserAgent.id)).where(
            or_(UserAgent.deleted_at.is_(None), UserAgent.deleted_at >= cycle_start_timestamp),
            UserAgent.created_at < cycle_end_timestamp
        )

        num_total_agents = session.exec(statement).one()

    top_N = math.ceil(2 * max([5, math.sqrt(num_total_agents)]))

    logger.info(f"top_N: {top_N}")

    total_emissions = get_total_cycle_emissions(cycle_end_timestamp)
    logger.info(f"total_emissions: {total_emissions}")

    total_agent_emissions = math.floor(total_emissions * 0.72)
    logger.info(f"total_agent_emissions: {total_emissions}")

    # Calculate the total scores of top agents

    with Session(engine) as session:
        statement = select(func.sum(UserAgentWeeklyEmissions.score)).where(
            UserAgentWeeklyEmissions.day == cycle_start_timestamp
        ).order_by(UserAgentWeeklyEmissions.score.desc()).limit(top_N)

        score_sum = session.exec(statement).one()

    logger.info(f"Score sum: {score_sum}")

    if score_sum == 0:
        raise Exception("score_sum is zero!")

    # Update agent emission in batch
    current_page = 0
    num_agent_processed = 0

    while True:
        with Session(engine) as session:
            statement = select(UserAgentWeeklyEmissions).where(
                UserAgentWeeklyEmissions.day == cycle_start_timestamp
            ).order_by(UserAgentWeeklyEmissions.score.desc()).offset(current_page * page_size).limit(page_size)

            top_agent_emissions = session.exec(statement).all()
            logger.info(f"num of top_agent_emissions in page {current_page}: {len(top_agent_emissions)}")

            for emission in top_agent_emissions:

                emission.emission = math.floor(total_agent_emissions * emission.score / score_sum)
                session.add(emission)

                num_agent_processed += 1

                if num_agent_processed >= top_N:
                    break

            session.commit()

            if len(top_agent_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"Updated emission for {num_agent_processed} agents!")


def get_total_cycle_emissions(cycle_end_timestamp: int) -> int:
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    week_num = (cycle_start_timestamp - settings.tn_emission_start) // (settings.tn_emission_interval_days * 86400)
    total_supply = 1000000000

    logger.info(f"Week num: {week_num}")

    if week_num > 250:
        return 0

    if week_num > 150:
        return math.floor(total_supply * 0.001)

    if week_num > 50:
        return math.floor(total_supply * 0.003)

    if week_num > 10:
        return math.floor(total_supply * 0.01)

    return math.floor(total_supply * 0.02)

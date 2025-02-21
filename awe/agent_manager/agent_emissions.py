from awe.db import engine
from sqlmodel import Session, select, or_
from awe.settings import settings
from datetime import datetime
import logging
from awe.models import UserAgent, UserAgentWeeklyEmissions, TotalCycleEmissions, UserStaking
from sqlalchemy import func
import math

logger = logging.getLogger("[Agent Emissions]")

page_size = 500


def update_total_cycle_emissions(cycle_end_timestamp: int, dry_run: bool):
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    with Session(engine) as session:

        statement = select(TotalCycleEmissions).where(
            TotalCycleEmissions.day == cycle_start_timestamp - settings.tn_emission_interval_days * 86400
        )

        last_total_cycle_emission = session.exec(statement).first()

        if last_total_cycle_emission is None and cycle_start_timestamp != settings.tn_emission_start:
            raise Exception("Missing previous emission data")

        # Check if the record already exists

        statement = select(TotalCycleEmissions).where(
            TotalCycleEmissions.day == cycle_start_timestamp
        )

        total_cycle_emission = session.exec(statement).first()

        if total_cycle_emission is None:
            total_cycle_emission = TotalCycleEmissions(
                day=cycle_start_timestamp
            )

        if last_total_cycle_emission is None:
            # The first emission
            # Let's hard code it
            logger.info("[Cycle Emission] The first emission")
            total_cycle_emission.total_emitted_before = 0
            total_cycle_emission.total_staked = 0
            total_cycle_emission.emission = 20000000 # 2% (20M) initial emission
        else:
            total_staked_now = get_total_staked(cycle_end_timestamp)
            total_cycle_emission.update_emission(last_total_cycle_emission.emission + last_total_cycle_emission.total_emitted_before, total_staked_now)

        session.add(total_cycle_emission)

        logger.info(f"[Cycle Emission] Total emitted before: {total_cycle_emission.total_emitted_before}, Total staked: {total_cycle_emission.total_staked}, Emission {total_cycle_emission.emission}")

        if dry_run:
            return

        session.commit()
        logger.info(f"[Cycle Emission] Emission generated!")


def distribute_all_agent_emissions(cycle_end_timestamp: int, dry_run: bool):

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

                logger.info(f"Agent emission: {emission.user_agent_id}: {emission.emission}")

                num_agent_processed += 1

                if num_agent_processed >= top_N:
                    break

            if not dry_run:
                session.commit()

            if len(top_agent_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"Updated emission for {num_agent_processed} agents!")


def get_total_cycle_emissions(cycle_end_timestamp: int) -> int:
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    with Session(engine) as session:
        statement = select(TotalCycleEmissions).where(
            TotalCycleEmissions.day == cycle_start_timestamp
        )

        total_cycle_emission = session.exec(statement).first()

        if total_cycle_emission is None:
            raise Exception("Missing emission data")

        return total_cycle_emission.emission


def get_total_staked(cycle_end_timestamp: int) -> int:

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.debug(f"Get total staking for cycle: [{start_datetime}, {end_datetime})")

    with Session(engine) as session:

        # Creator staking
        statement = select(func.sum(UserAgent.staking_amount)).where(
            UserAgent.created_at < cycle_end_timestamp,
            UserAgent.deleted_at.is_(None)
        )

        total_creator_staking = session.exec(statement).one()
        logger.debug(f"Total creator staking: {total_creator_staking}")

        # Player staking
        statement = select(func.sum(UserStaking.amount)).where(
            UserStaking.created_at < cycle_end_timestamp,
            or_(
                UserStaking.release_status.is_(None),
                UserStaking.released_at >= cycle_end_timestamp
            )
        )

        total_player_staking = session.exec(statement).one()
        logger.debug(f"Total player staking: {total_player_staking}")

        return total_creator_staking + total_player_staking

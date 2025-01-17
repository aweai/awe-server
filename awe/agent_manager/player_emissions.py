from sqlmodel import Session, select
from awe.db import engine
from awe.models import UserAgentWeeklyEmissions, TgUserDeposit, UserStaking, UserReferrals, PlayerWeeklyEmissions
from awe.settings import settings
import logging
from sqlalchemy import func
import math

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

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    total_player_emissions = math.floor(agent_emissions * 0.3)
    logger.info(f"total agent emissions: {agent_emissions}, total player emissions: {total_player_emissions}")

    # Update player scores
    current_page = 0
    while True:
        with Session(engine) as session:
            # Get player play sessions (num of payments)
            statement = select(TgUserDeposit.tg_user_id, func.count(TgUserDeposit.id)).where(
                TgUserDeposit.created_at >= cycle_start_timestamp,
                TgUserDeposit.created_at < cycle_end_timestamp,
                TgUserDeposit.user_agent_id == agent_id
            ).group_by(TgUserDeposit.tg_user_id).order_by(TgUserDeposit.tg_user_id.asc()).offset(current_page * page_size).limit(page_size)

            user_deposit_count = session.exec(statement).all()

            logger.info(f"{len(user_deposit_count)} players found for agent {agent_id}")

            player_ids = [tg_user_id for tg_user_id, _ in user_deposit_count]

            # Get player multiplier
            statement = select(UserReferrals).where(
                UserReferrals.tg_user_id.in_(player_ids)
            )

            player_referrals = session.exec(statement).all()
            player_multipliers = {}
            for player_referral in player_referrals:
                player_multipliers[player_referral.tg_user_id] = player_referral.get_multiplier()

            # Store player scores
            for tg_user_id, num_payment in user_deposit_count:

                if tg_user_id in player_multipliers:
                    score = num_payment * player_multipliers[tg_user_id]
                else:
                    score = num_payment

                player_weekly_emission = PlayerWeeklyEmissions(
                    user_agent_id=agent_id,
                    tg_user_id=tg_user_id,
                    day=cycle_start_timestamp,
                    score=score
                )

                session.add(player_weekly_emission)

            session.commit()

            if len(user_deposit_count) < page_size:
                break

            current_page += 1

    # Get total player scores
    with Session(engine) as session:
        statement = select(func.sum(PlayerWeeklyEmissions.score)).where(
            PlayerWeeklyEmissions.day == cycle_start_timestamp,
            PlayerWeeklyEmissions.user_agent_id == agent_id
        )

        total_score = session.exec(statement).one()
        logger.info(f"total score for agent {agent_id}: {total_score}")

    # Update player emissions
    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(PlayerWeeklyEmissions).where(
                PlayerWeeklyEmissions.day == cycle_start_timestamp,
                PlayerWeeklyEmissions.user_agent_id == agent_id
            ).order_by(PlayerWeeklyEmissions.id.asc()).offset(current_page * page_size).limit(page_size)

            player_emissions = session.exec(statement).all()

            logger.info(f"{len(player_emissions)} player emissions in page {current_page}")

            for player_emission in player_emissions:
                player_emission.emission = math.floor(total_player_emissions * player_emission.score / total_score)
                session.add(player_emission)

            session.commit()

            if len(player_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"All player emissions updated for agent {agent_id}")


def update_staker_emissions(cycle_end_timestamp: int):
    pass


def update_staker_emissions_for_agent(agent_id: int, cycle_end_timestamp: int):
    pass

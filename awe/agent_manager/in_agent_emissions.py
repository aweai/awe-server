from sqlmodel import Session, select, or_
from awe.db import engine
from awe.models import UserAgentWeeklyEmissions, \
    TgUserDeposit, UserStaking, UserReferrals, \
    PlayerWeeklyEmissions, StakerWeeklyEmissions, \
    UserAgent
from awe.models.user_staking import UserStakingStatus
from awe.settings import settings
import logging
from sqlalchemy import func
import math

logger = logging.getLogger("[Player Emissions]")

page_size = 500


def distribute_all_in_agent_emissions(cycle_end_timestamp: int):
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

                # Get player/creator emission division from agent data
                statement = select(UserAgent).where(UserAgent.id == agent_emission.user_agent_id)
                user_agent = session.exec(statement).first()
                creator_division = user_agent.awe_agent.awe_token_config.emission_creator_division
                player_division = 1 - creator_division

                # Player divistion
                if player_division != 0:
                    logger.info(f"Updating player emissions for agent {agent_emission.user_agent_id}")
                    update_player_emissions_for_agent(agent_emission.user_agent_id, cycle_end_timestamp, agent_emission.emission * 2 * player_division / 3 )
                else:
                    logger.info(f"No emission is given to players for agent {agent_emission.user_agent_id}")

                # Staker division
                logger.info(f"Updating staker emissions for agent {agent_emission.user_agent_id}")
                update_staker_emissions_for_agent(agent_emission.user_agent_id, cycle_end_timestamp, agent_emission.emission / 3)

                #TODO: Creator division

            if len(agent_emissions) < page_size:
                break

            current_page += 1


def update_player_emissions_for_agent(agent_id: int, cycle_end_timestamp: int, agent_emissions: int):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    total_player_emissions = math.floor(agent_emissions / 3) # 1/3 (30% )
    logger.info(f"total agent emissions: {agent_emissions}, total player emissions: {total_player_emissions}")

    # Update player scores
    current_page = 0
    while True:
        with Session(engine) as session:
            # Get player play sessions (num of payments)
            statement = select(TgUserDeposit.tg_user_id, func.count(TgUserDeposit.id)).where(
                TgUserDeposit.created_at >= cycle_start_timestamp,
                TgUserDeposit.created_at < cycle_end_timestamp,
                TgUserDeposit.user_agent_id == agent_id,
                TgUserDeposit.tx_hash.is_not(None),
                TgUserDeposit.tx_hash != ""
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

            # Get old records
            statement = select(PlayerWeeklyEmissions).where(
                PlayerWeeklyEmissions.user_agent_id==agent_id,
                PlayerWeeklyEmissions.tg_user_id.in_(player_ids),
                PlayerWeeklyEmissions.day==cycle_start_timestamp,
            )

            player_emissions = session.exec(statement).all()

            player_scores = {}
            for tg_user_id, num_payment in user_deposit_count:
                if tg_user_id in player_multipliers:
                    player_scores[tg_user_id] = num_payment * player_multipliers[tg_user_id]
                else:
                    player_scores[tg_user_id] = num_payment

            for player_emission in player_emissions:
                if player_emission.tg_user_id not in player_scores:
                    session.delete(player_emission)
                else:
                    player_emission.score = player_scores[player_emission.tg_user_id]
                    session.add(player_emission)
                    del player_scores[player_emission.tg_user_id]

            for tg_user_id in player_scores:
                player_weekly_emission = PlayerWeeklyEmissions(
                    user_agent_id=agent_id,
                    tg_user_id=tg_user_id,
                    day=cycle_start_timestamp,
                    score=player_scores[tg_user_id]
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
        logger.info(f"total player score for agent {agent_id}: {total_score}")

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


def update_staker_emissions_for_agent(agent_id: int, cycle_end_timestamp: int, agent_emissions: int):
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    total_staker_emissions = math.floor(agent_emissions * 0.3)
    logger.info(f"total agent emissions: {agent_emissions}, total staker emissions: {total_staker_emissions}")

    # Calculating staking scores

    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.user_agent_id == agent_id,
                UserStaking.status == UserStakingStatus.SUCCESS,
                UserStaking.created_at < cycle_start_timestamp,
                or_(
                    UserStaking.released_at.is_(None),
                    UserStaking.released_at >= cycle_end_timestamp
                )
            ).order_by(UserStaking.id.asc()).offset(current_page * page_size).limit(page_size)

            user_stakings = session.exec(statement).all()

            logger.info(f"{len(user_stakings)} user stakings for agent {agent_id} in page {current_page}")

            staking_ids = [staking.id for staking in user_stakings]

            staking_scores = {}
            for user_staking in user_stakings:
                staking_scores[user_staking.id] = [user_staking.tg_user_id, math.floor(user_staking.amount * user_staking.get_multiplier(cycle_end_timestamp))]

            # Get old records
            statement = select(StakerWeeklyEmissions).where(
                StakerWeeklyEmissions.staking_id.in_(staking_ids),
                StakerWeeklyEmissions.day==cycle_start_timestamp,
            )

            staking_emissions = session.exec(statement).all()

            # Update / delete old records
            for staking_emission in staking_emissions:
                if staking_emission.staking_id in staking_scores:
                    staking_emission.score = staking_scores[staking_emission.staking_id][1]
                    session.add(staking_emission)
                    del staking_scores[staking_emission.staking_id]
                else:
                    session.delete(staking_emission)

            # Add new records
            for staking_id in staking_scores:
                staking_emission = StakerWeeklyEmissions(
                    user_agent_id=agent_id,
                    staking_id=staking_id,
                    tg_user_id=staking_scores[staking_id][0],
                    score=staking_scores[staking_id][1],
                    day=cycle_start_timestamp
                )

                session.add(staking_emission)

            session.commit()

            if len(user_stakings) < page_size:
                break

            current_page += 1

    # Get total staking scores
    with Session(engine) as session:
        statement = select(func.sum(StakerWeeklyEmissions.score)).where(
            StakerWeeklyEmissions.day == cycle_start_timestamp,
            StakerWeeklyEmissions.user_agent_id == agent_id
        )

        total_score = session.exec(statement).one()
        logger.info(f"total staking score for agent {agent_id}: {total_score}")

    # Update staking emissions
    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(StakerWeeklyEmissions).where(
                StakerWeeklyEmissions.user_agent_id==agent_id,
                StakerWeeklyEmissions.day==cycle_start_timestamp,
            ).order_by(StakerWeeklyEmissions.id).offset(current_page * page_size).limit(page_size)

            staking_emissions = session.exec(statement).all()

            logger.info(f"{len(staking_emissions)} staking emissions for agent {agent_id} in page {current_page}")

            for staking_emission in staking_emissions:
                staking_emission.emission = total_staker_emissions * staking_emission.score / total_score
                session.add(staking_emission)

            session.commit()

            if len(staking_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"All staker emissions updated for agent {agent_id}")

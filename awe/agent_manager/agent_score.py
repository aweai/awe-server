
from awe.db import engine
from sqlmodel import Session, select, or_
from awe.models import UserStaking, UserAgentStatsUserDailyCounts, UserAgent, UserAgentWeeklyEmissions
from awe.models.user_staking import UserStakingStatus
from sqlalchemy import func
from typing import List, Dict, Tuple
import logging
from datetime import datetime
from awe.settings import settings
from sqlalchemy.orm import load_only

logger = logging.getLogger("[Agent Score]")

page_size = 500

def update_all_agent_scores(cycle_end_timestamp: int, dry_run: bool):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a) %H:%M:%S')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a) %H:%M:%S')

    logger.info(f"Updating agent scores for cycle: [{start_datetime} ({cycle_start_timestamp}), {end_datetime} ({cycle_end_timestamp}))")

    # Get max staking pool size and max players in this cycle
    max_staking_score, max_player_score = get_max_agent_scores(cycle_start_timestamp, cycle_end_timestamp)

    logger.info(f"max_staking_score: {max_staking_score}, max_player_score: {max_player_score}")


    # Check if we have already processed this cycle before
    with Session(engine) as session:
        statement = select(func.count(UserAgentWeeklyEmissions.id)).where(
            UserAgentWeeklyEmissions.day == cycle_start_timestamp
        )

        count = session.exec(statement).first()

        cycle_processed_before = count != 0

    logger.info(f"Cycle processed before: {cycle_processed_before}")

    current_page = 0

    while(True):

        with Session(engine) as session:
            statement = select(UserAgent).options(load_only(UserAgent.id, UserAgent.score)).where(
                or_(UserAgent.deleted_at.is_(None), UserAgent.deleted_at >= cycle_start_timestamp),
                UserAgent.created_at < cycle_end_timestamp
            ).order_by(UserAgent.id.asc()).offset(current_page * page_size).limit(page_size)

            user_agents = session.exec(statement).all()

            logger.info(f"Updating scores of {len(user_agents)} agents in page {current_page}")

            if len(user_agents) == 0:
                break

            current_page = current_page + 1

            agent_ids = [agent.id for agent in user_agents]

            logger.debug("Getting agent stakings...")
            agent_stakings = get_agent_stakings(agent_ids, cycle_end_timestamp)
            logger.debug(agent_stakings)

            logger.debug("Getting agent players...")
            agent_players = get_agent_players(agent_ids, cycle_end_timestamp)
            logger.debug(agent_players)

            user_agent_scores = {}

            logger.debug("Updating agent scores...")
            for user_agent in user_agents:

                agent_id = user_agent.id

                agent_staking_score = agent_stakings[agent_id] if agent_id in agent_stakings else 0
                agent_player_score = agent_players[agent_id] if agent_id in agent_players else 0

                if agent_staking_score == 0 and agent_player_score == 0:
                    agent_score = 0
                else:
                    staking_score = 0 if max_staking_score == 0 else agent_staking_score / max_staking_score
                    player_score = 0 if max_player_score == 0 else agent_player_score / max_player_score
                    agent_score = 0 if staking_score + player_score == 0 else 2 * staking_score * player_score / ( staking_score + player_score )
                    agent_score = int(agent_score * 10000)

                logger.info(f"Agent {agent_id} score {agent_score}")

                user_agent.score = agent_score

                session.add(user_agent)

                user_agent_scores[agent_id] = agent_score

                if not cycle_processed_before:
                    if agent_score != 0:
                        logger.debug("Adding weekly emission record")
                        # Record weekly agent emissions
                        weekly_emission = UserAgentWeeklyEmissions(
                            user_agent_id=agent_id,
                            day=cycle_start_timestamp,
                            score=agent_score
                        )
                        session.add(weekly_emission)
                    else:
                        logger.debug("Agent score zero. Skip record.")

            if not dry_run:
                session.commit()

        logger.info(f"{len(user_agents)} agent scores updated")

        if dry_run:
            return

        if cycle_processed_before:
            logger.info(f"Updating cycle emissions instead of creating")

            # Update instead of insert
            # Might missing some records
            with Session(engine) as session:
                statement = select(UserAgentWeeklyEmissions).where(
                    UserAgentWeeklyEmissions.user_agent_id.in_(user_agent_scores.keys()),
                    UserAgentWeeklyEmissions.day == cycle_start_timestamp
                )

                cycle_emissions = session.exec(statement).all()

                logger.info(f"{len(cycle_emissions)} agents has cycle emission record before.")

                # Update existing records
                for cycle_emission in cycle_emissions:
                    if user_agent_scores[cycle_emission.user_agent_id] != 0:
                        cycle_emission.score = user_agent_scores[cycle_emission.user_agent_id]
                        del user_agent_scores[cycle_emission.user_agent_id]
                        session.add(cycle_emission)
                    else:
                        # Delete the zero score record
                        session.delete(cycle_emission)

                logger.info(f"{len(user_agent_scores.keys())} agents doesn't have cycle emission record before.")

                # Add missing records
                for agent_id in user_agent_scores:
                    if user_agent_scores[agent_id] != 0:
                        cycle_emission = UserAgentWeeklyEmissions(
                            user_agent_id=agent_id,
                            day=cycle_start_timestamp,
                            score=user_agent_scores[agent_id]
                        )
                        session.add(cycle_emission)

                session.commit()

            logger.info(f"Cycle emissions updated!")

    logger.info(f"All agent scores updated")


def get_max_agent_scores(cycle_start_timestamp: int, cycle_end_timestamp: int) -> Tuple[int, int]:

    total_agents = 0
    max_staking_score = 0
    max_player_score = 0

    current_page = 0

    with Session(engine) as session:
        while(True):
            statement = select(UserAgent.id).where(
                or_(UserAgent.deleted_at.is_(None), UserAgent.deleted_at >= cycle_start_timestamp),
                UserAgent.created_at < cycle_end_timestamp
            ).order_by(UserAgent.id.asc()).offset(current_page * page_size).limit(page_size)

            agent_ids = session.exec(statement).all()

            logger.info(f"Getting max values: fetched {len(agent_ids)} agents for page {current_page}")

            if len(agent_ids) == 0:
                break

            total_agents = total_agents + len(agent_ids)

            current_page = current_page + 1

            logger.info("Getting agent stakings...")
            page_agent_stakings = get_agent_stakings(agent_ids, cycle_end_timestamp)
            logger.debug(page_agent_stakings)

            if len(page_agent_stakings.keys()) != 0:
                page_max_staking_score = max(page_agent_stakings.values())
                max_staking_score = max(page_max_staking_score, max_staking_score)

            logger.info("Getting agent players...")
            page_agent_players = get_agent_players(agent_ids, cycle_end_timestamp)
            logger.debug(page_agent_players)

            if len(page_agent_players.keys()) != 0:
                page_max_player_score = max(page_agent_players.values())
                max_player_score = max(page_max_player_score, max_player_score)


    logger.info(f"Total agents: {total_agents}")
    logger.info(f"Max agent staking score: {max_staking_score}")
    logger.info(f"Max agent player score: {max_player_score}")

    return max_staking_score, max_player_score


def get_agent_stakings(agent_ids: List[int], day_timestamp: int) -> Dict[int, int]:

    start_timestamp = day_timestamp - settings.tn_emission_interval_days * 86400
    end_timestamp = day_timestamp

    logger.info(f"Getting agent stakings for {len(agent_ids)} agents")
    logger.info(f"start before {start_timestamp} - end after {end_timestamp}")

    with Session(engine) as session:
        statement = select(UserStaking.user_agent_id, func.sum(UserStaking.amount)).where(
            UserStaking.user_agent_id.in_(agent_ids),
            or_(UserStaking.released_at.is_(None), UserStaking.released_at >= end_timestamp),
#            UserStaking.created_at < start_timestamp,
            UserStaking.status == UserStakingStatus.SUCCESS
        ).group_by(UserStaking.user_agent_id)

        user_stakings = session.exec(statement).all()

        logger.info(f"Total agent stakings: {len(user_stakings)}")

        agent_staking_scores = {}

        for agent_id, total_amount in user_stakings:
            agent_staking_scores[agent_id] = int(total_amount)


    return agent_staking_scores


def get_agent_players(agent_ids: List[int], day_timestamp: int) -> int:
    start_timestamp = day_timestamp - settings.tn_emission_interval_days * 86400
    end_timestamp = day_timestamp

    logger.info(f"Getting agent players for {len(agent_ids)} agents")

    with Session(engine) as session:

        statement = select(
            UserAgentStatsUserDailyCounts.user_agent_id,
            func.sum(UserAgentStatsUserDailyCounts.users)
        ).where(
            UserAgentStatsUserDailyCounts.user_agent_id.in_(agent_ids),
#            UserAgentStatsUserDailyCounts.day >= start_timestamp,
            UserAgentStatsUserDailyCounts.day < end_timestamp
        ).group_by(UserAgentStatsUserDailyCounts.user_agent_id)

        agent_users = session.exec(statement).all()

        logger.info(f"{len(agent_users)} agent records found.")

        agent_user_scores = {}
        for agent_id, agent_users in agent_users:
            agent_user_scores[agent_id] = int(agent_users)

        return agent_user_scores

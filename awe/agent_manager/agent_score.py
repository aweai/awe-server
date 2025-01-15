
from awe.db import engine
from sqlmodel import Session, select, or_
from awe.models import UserStaking, UserAgentStatsUserDailyCounts, UserAgent, UserAgentWeeklyEmissions
from sqlalchemy import func
from typing import List, Dict
import logging

logger = logging.getLogger("[Agent Score]")

# [start_timestamp, end_timestamp)
# >= start_timestamp, < end_timestamp
period = 7 * 86400


def update_all_agent_scores(day_timestamp: int):

    start_timestamp = day_timestamp - period
    end_timestamp = day_timestamp

    current_page = 0
    page_size = 500

    # Get max staking pool size and max players in this cycle (7 days)

    total_agents = 0
    max_staking_score = 0
    max_player_score = 0

    with Session(engine) as session:
        while(True):
            statement = select(UserAgent.id).where(
                or_(UserAgent.deleted_at.is_(None), UserAgent.deleted_at >= start_timestamp),
                UserAgent.created_at < end_timestamp
            ).order_by(UserAgent.id.asc()).offset(current_page * page_size).limit(page_size)

            agent_ids = session.exec(statement).all()

            if len(agent_ids) == 0:
                break

            total_agents = total_agents + len(agent_ids)

            current_page = current_page + 1

            page_agent_stakings = get_agent_stakings(agent_ids, day_timestamp)
            page_max_agent_id = max(page_agent_stakings)
            max_staking_score = max([page_agent_stakings[page_max_agent_id], max_staking_score])

            page_agent_players = get_agent_players(agent_ids, day_timestamp)
            page_max_agent_id = max(page_agent_players)
            max_player_score = max([page_agent_players[page_max_agent_id], max_player_score])

    logger.info(f"Total agents: {total_agents}")
    logger.info(f"Max agent staking score: {max_staking_score}")
    logger.info(f"Max agent player score: {max_player_score}")

    # Update agent score

    current_page = 0
    while(True):
        with Session(engine) as session:
            statement = select(UserAgent).where(
                or_(UserAgent.deleted_at.is_(None), UserAgent.deleted_at >= start_timestamp),
                UserAgent.created_at < end_timestamp
            ).order_by(UserAgent.id.asc()).offset(current_page * page_size).limit(page_size)

            user_agents = session.exec(statement).all()

            if len(user_agents) == 0:
                break

            current_page = current_page + 1

            agent_ids = [agent.id for agent in user_agents]

            agent_stakings = get_agent_stakings(agent_ids)
            agent_players = get_agent_players(agent_ids)

            for user_agent in user_agents:
                staking_score = agent_stakings[user_agent.id] / max_staking_score
                player_score = agent_players[user_agent.id] / max_player_score
                agent_score = 2 * staking_score * player_score / ( staking_score + player_score )
                agent_score = int(agent_score * 10000)

                user_agent.score = agent_score
                session.add(user_agent)

                # Record weekly agent emissions
                weekly_emission = UserAgentWeeklyEmissions(
                    user_agent_id=user_agent.id,
                    day=day_timestamp,
                    score=agent_score
                )

                session.add(weekly_emission)

            session.commit()


def get_agent_stakings(agent_ids: List[int], day_timestamp: int) -> Dict[int, int]:

    start_timestamp = day_timestamp - period
    end_timestamp = day_timestamp

    with Session(engine) as session:
        statement = select(UserStaking).where(
            UserStaking.user_agent_id.in_(agent_ids),
            or_(UserStaking.released_at.is_(None), UserStaking.released_at >= start_timestamp),
            UserStaking.created_at < end_timestamp
        )

        user_stakings = session.exec(statement).all()

        agent_staking_scores = {}

        for user_staking in user_stakings:
            agent_id = user_staking.user_agent_id

            if agent_id not in agent_staking_scores:
                agent_staking_scores[agent_id] = 0

            agent_staking_scores[agent_id] = agent_staking_scores[agent_id] + user_staking.amount * user_staking.get_multiplier(day_timestamp)

    return agent_staking_scores


def get_agent_players(agent_ids: List[int], day_timestamp: int) -> int:
    start_timestamp = day_timestamp - period
    end_timestamp = day_timestamp
    with Session(engine) as session:

        statement = select(
            [
                UserAgentStatsUserDailyCounts.user_agent_id,
                func.sum(UserAgentStatsUserDailyCounts.users).label("users")
            ]).select_from(UserAgentStatsUserDailyCounts).where(
                UserAgentStatsUserDailyCounts.user_agent_id.in_(agent_ids),
                UserAgentStatsUserDailyCounts.day >= start_timestamp,
                UserAgentStatsUserDailyCounts.day < end_timestamp
            ).group_by(UserAgentStatsUserDailyCounts.user_agent_id)

        agent_users = session.exec(statement).all()

        agent_user_scores = {}
        for agent_user in agent_users:
            agent_user_scores[agent_user["user_agent_id"]] = agent_user["users"]

        return agent_user_scores

from awe.db import engine
from sqlmodel import Session, select, or_
from awe.settings import settings
from datetime import datetime
import logging
from awe.models import UserAgent, UserAgentData, UserAgentWeeklyEmissions, TotalCycleEmissions, UserStaking
from awe.models.user_staking import UserStakingStatus
from awe.models import TgUserAccount, PlayerWeeklyEmissions, CreatorWeeklyEmissions, StakerWeeklyEmissions, StakerGlobalWeeklyEmissions
from sqlalchemy import func
import math


# Emissions

#	• Stakers - 8%
#	• Top - 60.3 % (67% * 0.9)
#	• New - 18% (20% * 0.9)
#	• LP - 5%
#	• Treasury - 8.7% (67% * 0.1 + 20% * 0.1, extracted from below)

# In-Memegent Emissions:
#	• Stakers - 1/3
#	• Creators + Players - 2/3
#	• Treasury - 0 (Moved above)


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


def distribute_global_staking_emissions(cycle_end_timestamp: int, dry_run: bool):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400
    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.info(f"Updating global staking emissions for cycle: [{start_datetime}, {end_datetime})")

    total_cycle_emissions = get_total_cycle_emissions(cycle_end_timestamp)

    total_global_staking_emissions = math.floor(total_cycle_emissions * 0.08) # 8% to stakers

    logger.info(f"total cycle emissions: {total_cycle_emissions}, total global staking emissions: {total_global_staking_emissions}")

    # calculate staking scores
    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(UserStaking).where(
                UserStaking.status == UserStakingStatus.SUCCESS,
                UserStaking.created_at < cycle_start_timestamp,
                or_(
                    UserStaking.released_at.is_(None),
                    UserStaking.released_at >= cycle_end_timestamp
                )
            ).order_by(UserStaking.id.asc()).offset(current_page * page_size).limit(page_size)

            user_stakings = session.exec(statement).all()

            logger.info(f"{len(user_stakings)} user stakings in page {current_page}")

            staking_ids = [staking.id for staking in user_stakings]

            logger.info("global staking scores")

            staking_scores = {}
            for user_staking in user_stakings:
                multiplier = user_staking.get_multiplier(cycle_end_timestamp)
                staking_score = math.floor(user_staking.amount * multiplier)
                logger.info(f"[Global Staking Score] user id: {user_staking.tg_user_id}, staking_id: {user_staking.id}, staking_amount: {user_staking.amount}, multiplier: {multiplier}, staking_score: {staking_score}")
                staking_scores[user_staking.id] = [user_staking.tg_user_id, staking_score]

            # Get old records
            statement = select(StakerGlobalWeeklyEmissions).where(
                StakerGlobalWeeklyEmissions.staking_id.in_(staking_ids),
                StakerGlobalWeeklyEmissions.day==cycle_start_timestamp,
            )

            global_staking_emissions = session.exec(statement).all()

            # Update / delete old records
            for global_staking_emission in global_staking_emissions:
                if global_staking_emission.staking_id in staking_scores:
                    global_staking_emission.score = staking_scores[global_staking_emission.staking_id][1]
                    session.add(global_staking_emission)
                    del staking_scores[global_staking_emission.staking_id]
                else:
                    session.delete(global_staking_emission)

            # Add new records
            for staking_id in staking_scores:
                staking_emission = StakerGlobalWeeklyEmissions(
                    staking_id=staking_id,
                    tg_user_id=staking_scores[staking_id][0],
                    score=staking_scores[staking_id][1],
                    day=cycle_start_timestamp
                )

                session.add(staking_emission)

            if not dry_run:
                session.commit()

            if len(user_stakings) < page_size:
                break

            current_page += 1

    # Get total staking scores
    with Session(engine) as session:
        statement = select(func.sum(StakerGlobalWeeklyEmissions.score)).where(
            StakerGlobalWeeklyEmissions.day == cycle_start_timestamp
        )

        total_score = session.exec(statement).one()
        logger.info(f"total global staking score {total_score}")

    # Update staking emissions
    current_page = 0
    while True:
        with Session(engine) as session:
            statement = select(StakerGlobalWeeklyEmissions).where(
                StakerGlobalWeeklyEmissions.day==cycle_start_timestamp,
            ).order_by(StakerGlobalWeeklyEmissions.id).offset(current_page * page_size).limit(page_size)

            global_staking_emissions = session.exec(statement).all()

            logger.info(f"{len(global_staking_emissions)} staking emissions in page {current_page}")

            for global_staking_emission in global_staking_emissions:
                global_staking_emission.emission = math.floor(total_global_staking_emissions * global_staking_emission.score / total_score)
                logger.info(f"[Global Staking Emissions] staking id: {global_staking_emission.id}, staking score: {global_staking_emission.score}, emission: {global_staking_emission.emission}")
                session.add(global_staking_emission)

            if not dry_run:
                session.commit()

            if len(global_staking_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"All global staking emissions updated")


# Top Agent Emissions
def distribute_top_agent_emissions(cycle_end_timestamp: int, dry_run: bool):

    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.info(f"Updating top agent emissions for cycle: [{start_datetime}, {end_datetime})")

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

    total_agent_emissions = math.floor(total_emissions * 0.603) # 60.3% (67% * 0.9)
    logger.info(f"total_agent_emissions: {total_agent_emissions}")

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


def distribute_new_agent_emissions(cycle_end_timestamp: int, dry_run: bool):

    # Right now we simply reward all agents
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.info(f"Updating new agent emissions for cycle: [{start_datetime}, {end_datetime})")

    total_emissions = get_total_cycle_emissions(cycle_end_timestamp)
    logger.info(f"total_emissions: {total_emissions}")

    total_agent_emissions = math.floor(total_emissions * 0.18) # 18% (20% * 0.9)
    logger.info(f"total_agent_emissions: {total_agent_emissions}")

    # Calculate the total scores of all new agents

    with Session(engine) as session:
        statement = select(func.sum(UserAgentWeeklyEmissions.score)).where(
            UserAgentWeeklyEmissions.day == cycle_start_timestamp,
            UserAgentWeeklyEmissions.score != 0
        )

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
                UserAgentWeeklyEmissions.day == cycle_start_timestamp,
                UserAgentWeeklyEmissions.score != 0
            ).offset(current_page * page_size).limit(page_size)

            new_agent_emissions = session.exec(statement).all()
            logger.info(f"num of new_agent_emissions in page {current_page}: {len(new_agent_emissions)}")

            for emission in new_agent_emissions:

                new_agent_emission = math.floor(total_agent_emissions * emission.score / score_sum)

                logger.info(f"New agent emission: {emission.user_agent_id}: {new_agent_emission}")
                logger.info(f"Total agent emission: {emission.emission + new_agent_emission}")

                emission.emission = UserAgentWeeklyEmissions.emission + new_agent_emission
                session.add(emission)

                num_agent_processed += 1

            if not dry_run:
                session.commit()

            if len(new_agent_emissions) < page_size:
                break

            current_page += 1

    logger.info(f"Updated emission for {num_agent_processed} agents!")



def update_all_emission_account_balances(cycle_end_timestamp: int, dry_run: bool):
    cycle_start_timestamp = cycle_end_timestamp - settings.tn_emission_interval_days * 86400

    start_datetime = datetime.fromtimestamp(cycle_start_timestamp).strftime('%Y-%m-%d(%a)')
    end_datetime = datetime.fromtimestamp(cycle_end_timestamp).strftime('%Y-%m-%d(%a)')

    logger.info(f"Updating account balances for emissions cycle: [{start_datetime}, {end_datetime})")

    #TODO: paging for large scale

    # Global stakers emissions
    update_global_staking_emission_account_balances(cycle_start_timestamp, dry_run)

    # Memegent - players
    update_agent_player_emission_account_balances(cycle_start_timestamp, dry_run)

    # Memegent - creators
    update_agent_creator_emission_account_balances(cycle_start_timestamp, dry_run)

    # Memegent - stakers
    update_agent_staking_emission_account_balances(cycle_start_timestamp, dry_run)


def update_global_staking_emission_account_balances(cycle_start_timestamp: int, dry_run: bool):
    logger.info(f"Updating Global staking reward balances")

    with Session(engine) as session:
        statement = select(StakerGlobalWeeklyEmissions).where(StakerGlobalWeeklyEmissions.day == cycle_start_timestamp)
        staker_emissions = session.exec(statement).all()

        tg_user_ids = []
        tg_user_emissions = {}

        for staker_emission in staker_emissions:
            # Might be multiple staking for a single user
            tg_user_id = staker_emission.tg_user_id

            logger.info(f"Global staking emissions: {tg_user_id}: {staker_emission.emission}")

            if tg_user_id not in tg_user_emissions:
                tg_user_emissions[tg_user_id] = 0
                tg_user_ids.append(tg_user_id)

            tg_user_emissions[tg_user_id] += staker_emission.emission

            logger.info(f"Global user emissions: {tg_user_id}: {tg_user_emissions[tg_user_id]}")

        statement = select(TgUserAccount).where(TgUserAccount.tg_user_id.in_(tg_user_ids))
        tg_user_accounts = session.exec(statement).all()

        for tg_user_account in tg_user_accounts:
            logger.info(f"Adding balance for user {tg_user_account.tg_user_id}: {tg_user_account.balance} -> {tg_user_emissions[tg_user_account.tg_user_id] + tg_user_account.balance}")
            tg_user_account.balance = TgUserAccount.balance + tg_user_emissions[tg_user_account.tg_user_id]
            session.add(tg_user_account)

        if not dry_run:
            session.commit()

    logger.info(f"Global staking reward balances updated!")


def update_agent_player_emission_account_balances(cycle_start_timestamp: int, dry_run: bool):
    logger.info(f"Update agent player emission balances")
    with Session(engine) as session:
        statement = select(PlayerWeeklyEmissions).where(PlayerWeeklyEmissions.day == cycle_start_timestamp)
        player_emissions = session.exec(statement).all()
        tg_user_ids = []
        tg_user_emissions = {}

        for player_emission in player_emissions:
            # Might be multiple emissions for a single user in multiple agents
            tg_user_id = player_emission.tg_user_id

            logger.info(f"Single agent player emissions: {tg_user_id}: {player_emission.emission}")

            if tg_user_id not in tg_user_emissions:
                tg_user_emissions[tg_user_id] = 0
                tg_user_ids.append(tg_user_id)

            tg_user_emissions[player_emission.tg_user_id] += player_emission.emission

            logger.info(f"All agent player emissions: {tg_user_id}: {tg_user_emissions[tg_user_id]}")

        statement = select(TgUserAccount).where(TgUserAccount.tg_user_id.in_(tg_user_ids))
        tg_user_accounts = session.exec(statement).all()

        for tg_user_account in tg_user_accounts:
            logger.info(f"Adding balance for user {tg_user_account.tg_user_id}: {tg_user_account.balance} -> {tg_user_emissions[tg_user_account.tg_user_id] + tg_user_account.balance}")
            tg_user_account.balance = TgUserAccount.balance + tg_user_emissions[tg_user_account.tg_user_id]
            session.add(tg_user_account)

        if not dry_run:
            session.commit()

    logger.info(f"Agent player emission balances updated!")


def update_agent_creator_emission_account_balances(cycle_start_timestamp: int, dry_run: bool):
    logger.info(f"Update agent creator emission balances")
    with Session(engine) as session:
        statement = select(CreatorWeeklyEmissions).where(CreatorWeeklyEmissions.day == cycle_start_timestamp)
        creator_emissions = session.exec(statement).all()

        user_agent_ids = []
        user_agent_emissions = {}

        for creator_emission in creator_emissions:
            user_agent_ids.append(creator_emission.user_agent_id)
            user_agent_emissions[creator_emission.user_agent_id] = creator_emission.emission
            logger.info(f"Agent emissions: {creator_emission.user_agent_id}: {user_agent_emissions[creator_emission.user_agent_id]}")

        statement = select(UserAgentData).where(UserAgentData.user_agent_id.in_(user_agent_ids))
        user_agent_data = session.exec(statement).all()

        for agent_data in user_agent_data:
            logger.info(f"Adding balance for creator of agent {agent_data.user_agent_id}: {agent_data.awe_token_creator_balance} -> {agent_data.awe_token_creator_balance + user_agent_emissions[agent_data.user_agent_id]}")
            agent_data.awe_token_creator_balance = UserAgentData.awe_token_creator_balance + user_agent_emissions[agent_data.user_agent_id]
            session.add(agent_data)

        if not dry_run:
            session.commit()

    logger.info(f"Agent creator emission balances updated!")


def update_agent_staking_emission_account_balances(cycle_start_timestamp, dry_run):
    logger.info(f"Updating Global staking reward balances")

    with Session(engine) as session:
        statement = select(StakerWeeklyEmissions).where(StakerWeeklyEmissions.day == cycle_start_timestamp)
        staking_emissions = session.exec(statement).all()

        tg_user_ids = []
        tg_user_emissions = {}

        for staking_emission in staking_emissions:
            # Might be multiple staking for a single user
            tg_user_id = staking_emission.tg_user_id

            logger.info(f"Agent staking emissions: {tg_user_id}: {staking_emission.emission}")

            if tg_user_id not in tg_user_emissions:
                tg_user_emissions[tg_user_id] = 0
                tg_user_ids.append(tg_user_id)

            tg_user_emissions[tg_user_id] += staking_emission.emission

            logger.info(f"User emissions: {tg_user_id}: {tg_user_emissions[tg_user_id]}")

        statement = select(TgUserAccount).where(TgUserAccount.tg_user_id.in_(tg_user_ids))
        tg_user_accounts = session.exec(statement).all()

        for tg_user_account in tg_user_accounts:
            logger.info(f"Adding balance for user {tg_user_account.tg_user_id}: {tg_user_account.balance} -> {tg_user_emissions[tg_user_account.tg_user_id] + tg_user_account.balance}")
            tg_user_account.balance = TgUserAccount.balance + tg_user_emissions[tg_user_account.tg_user_id]
            session.add(tg_user_account)

        if not dry_run:
            session.commit()

    logger.info(f"Agent staking reward balances updated!")


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

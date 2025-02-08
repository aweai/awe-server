
from sqlmodel import Session
from awe.models import UserAgentStatsTokenTransferDailyCounts, UserAgentStatsPaymentDailyCounts, UserAgentData, UserAgentStatsStakingDailyCounts

def record_user_payment(user_agent_id: int, pool_amount: int, creator_amount: int, session: Session):
    # Add payment daily count
    UserAgentStatsPaymentDailyCounts.add_payment(user_agent_id, pool_amount, creator_amount, session)


def record_user_withdraw(user_agent_id: int, amount: int, session: Session):

    # Add token transfer daily count
    UserAgentStatsTokenTransferDailyCounts.add_transfer(user_agent_id, amount, session)

    # Add token transfer total count
    UserAgentData.add_awe_token_transfer_stats(user_agent_id, amount, session)


def record_user_staking(user_agent_id: int, address: str, amount: int, session: Session):
    UserAgentStatsStakingDailyCounts.add_staking(user_agent_id, amount, session)
    UserAgentData.add_staking(user_agent_id, amount, session)


def record_user_staking_release(user_agent_id: int, address: str, amount: int, session: Session):
    UserAgentStatsStakingDailyCounts.add_releasing(user_agent_id, amount, session)
    UserAgentData.release_staking(user_agent_id, amount, session)

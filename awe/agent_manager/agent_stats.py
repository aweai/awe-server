
from sqlmodel import Session
from awe.models import TgUserWithdraw, TgUserDeposit, UserAgentStatsTokenTransferDailyCounts, UserAgentStatsPaymentDailyCounts, UserAgentData, UserAgentStatsStakingDailyCounts
from awe.models.utils import get_day_as_timestamp
from .cached_distinct_item_set import CachedDistinctItemSet

user_withraw_address_set = CachedDistinctItemSet("USER_WITHDRAW", TgUserWithdraw, TgUserWithdraw.address)
user_payment_address_set = CachedDistinctItemSet("USER_PAYMENT", TgUserDeposit, TgUserDeposit.address)

def record_user_payment(user_agent_id: int, address: str, pool_amount: int, creator_amount: int, session: Session):

    day = get_day_as_timestamp()
    is_new_address_today, _ = user_payment_address_set.add_item(day, user_agent_id, address)

    # Add payment daily count
    UserAgentStatsPaymentDailyCounts.add_payment(user_agent_id, pool_amount, creator_amount, is_new_address_today, session)

    if creator_amount != 0:
        # Add total income share
        UserAgentData.add_income_shares(user_agent_id, creator_amount, session)


def record_user_withdraw(user_agent_id: int, address: str, amount: int, session: Session):

    day = get_day_as_timestamp()
    is_new_address_today, is_new_address_total = user_withraw_address_set.add_item(day, user_agent_id, address)

    # Add token transfer daily count
    UserAgentStatsTokenTransferDailyCounts.add_transfer(user_agent_id, amount, is_new_address_today, session)

    # Add token transfer total count
    UserAgentData.add_awe_token_transfer_stats(user_agent_id, amount, is_new_address_total, session)


def record_user_staking(user_agent_id: int, address: str, amount: int, session: Session):
    UserAgentStatsStakingDailyCounts.add_staking(user_agent_id, amount, session)
    UserAgentData.add_staking(user_agent_id, amount, session)


def record_user_staking_release(user_agent_id: int, address: str, amount: int):
    UserAgentStatsStakingDailyCounts.add_releasing(user_agent_id, amount)
    UserAgentData.release_staking(user_agent_id, amount)

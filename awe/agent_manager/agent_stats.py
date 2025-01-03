
from awe.models import TgUserWithdraw, TgUserDeposit, UserAgentStatsTokenTransferDailyCounts, UserAgentStatsPaymentDailyCounts, UserAgentData, UserAgentStatsStakingDailyCounts
from awe.models.utils import get_day_as_timestamp
from .cached_distinct_item_set import CachedDistinctItemSet
from awe.settings import settings

user_withraw_address_set = CachedDistinctItemSet("USER_WITHDRAW", TgUserWithdraw, TgUserWithdraw.address)
user_payment_address_set = CachedDistinctItemSet("USER_PAYMENT", TgUserDeposit, TgUserDeposit.address)

def record_user_payment(user_agent_id: int, address: str, amount: int):

    day = get_day_as_timestamp()
    is_new_address_today, is_new_address_total = user_payment_address_set.add_item(day, user_agent_id, address)

    # Add payment daily count
    UserAgentStatsPaymentDailyCounts.add_payment(user_agent_id, amount, is_new_address_today)

    # Add total income share
    _, creator_share, _ = settings.tn_share_user_payment(amount)
    UserAgentData.add_income_shares(user_agent_id, creator_share)


def record_user_withdraw(user_agent_id: int, address: str, amount: int):

    day = get_day_as_timestamp()
    is_new_address_today, is_new_address_total = user_withraw_address_set.add_item(day, user_agent_id, address)

    # Add token transfer daily count
    UserAgentStatsTokenTransferDailyCounts.add_transfer(user_agent_id, amount, is_new_address_today)

    # Add token transfer total count
    UserAgentData.add_awe_token_transfer_stats(user_agent_id, amount, is_new_address_total)

def record_user_staking(user_agent_id: int, address: str, amount: int):
    UserAgentStatsStakingDailyCounts.add_staking(user_agent_id, amount)
    UserAgentData.add_staking(user_agent_id, amount)

def record_user_staking_release(user_agent_id: int, address: str, amount: int):
    UserAgentStatsStakingDailyCounts.add_releasing(user_agent_id, amount)
    UserAgentData.release_staking(user_agent_id, amount)

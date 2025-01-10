from sqlmodel import SQLModel, Field, select, Session
from typing import Annotated, Optional
from typing_extensions import Self
from awe.db import engine
import random
import string
import math
import logging

logger = logging.getLogger("[User Referrals]")

class UserAlreadyReferred(Exception):
    pass

class CodeNotFound(Exception):
    pass


def generate_random_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

class UserReferrals(SQLModel, table=True):
    id: Annotated[Optional[int], Field(primary_key=True)]
    tg_user_id: Annotated[str, Field(index=True, nullable=False)]
    code: Annotated[str, Field(unique=True, nullable=False, default_factory=generate_random_code)]
    num_referrals: Annotated[int, Field(nullable=False, default=0)] = 0
    num_activated_referrals: Annotated[int, Field(nullable=False, default=0)] = 0
    referred_by: Annotated[int, Field(nullable=True)]
    activated: Annotated[bool, Field(nullable=False, default=False)] = False

    @classmethod
    def get_or_create_user_referrals(cls, tg_user_id: str) -> Self:
        with Session(engine) as session:

            statement = select(UserReferrals).where(
                UserReferrals.tg_user_id == tg_user_id
            )

            user_referrals = session.exec(statement).first()

            if user_referrals is None:
                user_referrals = UserReferrals(
                    tg_user_id=tg_user_id
                )

                session.add(user_referrals)
                session.commit()
                session.refresh(user_referrals)

            return user_referrals


    def get_multiplier(self) -> int:
        multiplier = 28.5 * math.log10(self.num_activated_referrals + 1) + 1
        if multiplier > 100:
            multiplier = 100

        return int(multiplier)

    @classmethod
    def activate(cls, tg_user_id: str):

        with Session(engine) as session:
            target_statement = select(UserReferrals).where(
                UserReferrals.tg_user_id == tg_user_id
            )

            target_user_referrals = session.exec(target_statement).first()

            if target_user_referrals is None or target_user_referrals.activated == True:
                return

            target_user_referrals.activated = True
            session.add(target_user_referrals)

            # Prevent loop in the referral chain
            referral_ids = {
                target_user_referrals.id: 1
            }

            # Trace the referral chain up
            while target_user_referrals.referred_by is not None and target_user_referrals.referred_by not in referral_ids:
                referral_ids[target_user_referrals.referred_by] = 1

                next_target_statement = select(UserReferrals).where(
                    UserReferrals.id == target_user_referrals.referred_by
                )

                target_user_referrals = session.exec(next_target_statement).first()
                target_user_referrals.num_activated_referrals = UserReferrals.num_activated_referrals + 1
                session.add(target_user_referrals)

            session.commit()


    @classmethod
    def add_referred_by(cls, tg_user_id: str, code: str):

        with Session(engine) as session:

            target_statement = select(UserReferrals).where(
                UserReferrals.code == code
            )

            target_user_referrals = session.exec(target_statement).first()

            if target_user_referrals is None:
                raise CodeNotFound()

            source_user_referrals = cls.get_or_create_user_referrals(tg_user_id)

            if source_user_referrals.referred_by is not None:
                raise UserAlreadyReferred()

            source_user_referrals.referred_by = target_user_referrals.id
            session.add(source_user_referrals)

            logger.debug(f"Updating target user referral: {target_user_referrals.id}")
            target_user_referrals.num_referrals = UserReferrals.num_referrals + 1
            session.add(target_user_referrals)

            # Prevent loop in the referral chain
            referral_ids = {
                target_user_referrals.id: 1,
                source_user_referrals.id: 1
            }

            logger.debug(referral_ids)

            # Trace the referral chain up
            while target_user_referrals.referred_by is not None \
                  and target_user_referrals.referred_by not in referral_ids:
                referral_ids[target_user_referrals.referred_by] = 1

                next_target_statement = select(UserReferrals).where(
                    UserReferrals.id == target_user_referrals.referred_by
                )

                target_user_referrals = session.exec(next_target_statement).first()

                logger.debug(f"Updating target user referral: {target_user_referrals.id}")
                target_user_referrals.num_referrals = UserReferrals.num_referrals + 1
                session.add(target_user_referrals)

            session.commit()
            session.refresh(source_user_referrals)

            return source_user_referrals

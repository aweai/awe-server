from sqlmodel import SQLModel, Field
from .utils import unix_timestamp_in_seconds
from typing import Annotated
import math


class TotalCycleEmissions(SQLModel, table=True):
    id: int | None = Field(primary_key=True)
    day: Annotated[int, Field(index=True, nullable=False)]
    total_staked: Annotated[int, Field(index=False, nullable=False)]
    total_emitted_before: Annotated[int, Field(index=False, nullable=False)]
    emission: Annotated[int, Field(index=False, nullable=False)]
    created_at: Annotated[int, Field(nullable=False, default_factory=unix_timestamp_in_seconds)]

    def update_emission(
            self,
            awe_total_emitted_before: int,
            awe_total_staked: int):

        self.total_emitted_before = awe_total_emitted_before
        self.total_staked = awe_total_staked

        awe_remaining = 1000000000 - self.total_emitted_before
        staked_portion = awe_total_staked / self.total_emitted_before
        max_portion = max(0.3, staked_portion)

        self.emission = int(math.floor(0.015 * awe_remaining * max_portion))

"""
Exposure model and calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .context import RiskContext
from .model import RiskRequest


@dataclass(frozen=True)
class Exposure:

    entity_id: str

    asset: str

    value: float

    exposure_type: str


class ExposureCalculator:
    def projected_exposure(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Decimal:
        current = (
            context.current_position
            * request.price
        )

        incoming = (
            request.quantity
            * request.price
        )

        return current + incoming
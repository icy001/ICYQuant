"""
Portfolio concentration check.
"""

from __future__ import annotations

from decimal import Decimal


class ConcentrationChecker:
    def check(
        self,
        factor_exposure,
        max_exposure,
    ):
        for factor, value in factor_exposure.items():
            if value > max_exposure:
                return False

        return True
"""
Strategy promotion controller.
"""

from __future__ import annotations


class PromotionController:
    def promote(
        self,
        result,
    ):
        if result.passed:
            return "APPROVED"

        return "REJECTED"
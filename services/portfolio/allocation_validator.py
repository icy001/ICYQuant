"""
Allocation validation.
"""

from decimal import Decimal


class AllocationValidator:
    def validate(
        self,
        targets,
    ):
        total = sum(target.target_weight for target in targets)
        return total == Decimal("1")
"""Capital management engine for investor capital and cash oversight."""

from __future__ import annotations


class CapitalManagementEngine:
    """Manages fund-level capital including investor capital, cash balance,
    and margin usage.
    """

    def allocate(self, capital: float, allocation: dict) -> dict:
        """Allocate capital according to a target allocation.

        Args:
            capital: Total capital available.
            allocation: Target allocation weights.

        Returns:
            Dict with ``capital`` and ``allocation`` keys.
        """
        return {
            "capital": capital,
            "allocation": allocation,
        }

"""AI CIO service — top-level entry point for the Chief Investment Officer."""

from __future__ import annotations

from .allocation import AssetAllocationEngine


class AICIOService:
    """Top-level service for the AI Chief Investment Officer Engine.

    Sits above the Investment Committee, responsible for global capital
    allocation strategy and portfolio-level decision making.
    """

    def __init__(self, allocator: AssetAllocationEngine) -> None:
        self.allocator = allocator

    def allocate(self, assets: list[str]) -> dict[str, float]:
        """Execute capital allocation across asset classes.

        Args:
            assets: List of asset class identifiers.

        Returns:
            Dict mapping assets to allocation weights.
        """
        return self.allocator.allocate(assets)

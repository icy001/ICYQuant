"""Asset allocation engine for capital distribution across asset classes."""

from __future__ import annotations


class AssetAllocationEngine:
    """Core engine for strategic asset allocation.

    Distributes capital across equity, bonds, commodities, currency,
    alternative assets, and cash based on the CIO strategy and market
    regime.
    """

    def allocate(self, assets: list[str]) -> dict[str, float]:
        """Allocate capital equally across asset classes.

        Args:
            assets: List of asset class identifiers.

        Returns:
            Dict mapping each asset to its allocation weight.
        """
        return {asset: 1 / len(assets) for asset in assets}

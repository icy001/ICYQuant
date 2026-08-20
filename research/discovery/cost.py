"""Per-asset transaction cost model for Discovery Lab v1.

Commission + spread + slippage are folded into a single one-way rate (in bps)
per unit of notional.  A round trip therefore pays ``2 * one_way_bps``.

Assets with wide spreads (gold, silver, HSTECH, A-shares) are charged more so
Discovery cannot systematically prefer high-turnover strategies on cheap
assets.  Values are documented assumptions fixed in ``spec.COST_CONFIG``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .spec import COST_CONFIG, DISCOVERY_SPEC_V1


@dataclass(frozen=True)
class CostModel:
    """Cost model derived from the sealed spec cost config.

    Parameters
    ----------
    cost_config : dict[str, dict[str, float]]
        ``{asset: {"commission_bps": float, "spread_bps": float,
                   "slippage_bps": float}}``
    """

    cost_config: dict[str, dict[str, float]] = field(
        default_factory=lambda: COST_CONFIG)

    def one_way_bps(self, asset: str) -> float:
        """Total one-way cost in basis points for a single asset."""
        cfg = self.cost_config[asset]
        return cfg["commission_bps"] + cfg["spread_bps"] + cfg["slippage_bps"]

    def round_trip_bps(self, asset: str) -> float:
        """Round-trip cost in basis points (entry + exit)."""
        return 2.0 * self.one_way_bps(asset)

    def one_way_fraction(self, asset: str) -> float:
        """One-way cost as a fraction of notional."""
        return self.one_way_bps(asset) / 10_000.0

    def net_return(self, asset: str, gross_return: float) -> float:
        """Net simple return after paying the round-trip cost once.

        A round trip costs ``2c`` of notional; the net multiplier is
        ``(1 + gross) * (1 - c)**2``.
        """
        c = self.one_way_fraction(asset)
        return (1.0 + gross_return) * (1.0 - c) ** 2 - 1.0

    def breakdown(self, asset: str) -> dict[str, float]:
        return dict(self.cost_config[asset])

    def to_dict(self, asset: str) -> dict[str, object]:
        return {
            "asset": asset,
            "commission_bps": self.cost_config[asset]["commission_bps"],
            "spread_bps": self.cost_config[asset]["spread_bps"],
            "slippage_bps": self.cost_config[asset]["slippage_bps"],
            "one_way_bps": self.one_way_bps(asset),
            "round_trip_bps": self.round_trip_bps(asset),
        }


# Default instance matching the sealed v1 spec.
DEFAULT_COST_MODEL = CostModel(cost_config=DISCOVERY_SPEC_V1.cost_config)

"""
Attribution result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionResult:
    pnl_by_strategy: dict
    pnl_by_factor: dict
    risk_by_asset: dict
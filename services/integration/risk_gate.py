"""
Risk Gate — checks risk constraints before a trade proceeds.

Commit 21 Part 1.1: validates Exposure, Leverage, Position, Drawdown,
Concentration, Liquidity, and Limits before allowing flow to continue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .control_gate import ControlGate
from .control_context import TradingControlContext
from .control_result import ControlResult, GateStatus


@dataclass
class RiskGateConfig:
    """Configuration for Risk Gate thresholds."""

    max_exposure_pct: float = 1.0          # Max portfolio exposure ratio
    max_leverage: float = 3.0              # Max leverage ratio
    max_drawdown_pct: float = 0.20         # Max drawdown from peak
    max_concentration_pct: float = 0.25    # Max single-position concentration
    min_liquidity_score: float = 0.3       # Minimum liquidity score
    max_position_size_pct: float = 0.10    # Max position size as % of portfolio
    enabled_checks: Dict[str, bool] = field(default_factory=lambda: {
        "exposure": True,
        "leverage": True,
        "drawdown": True,
        "concentration": True,
        "liquidity": True,
        "position_size": True,
    })


@dataclass
class RiskGate(ControlGate):
    """Risk Gate — validates risk constraints.

    Checks:
      - Exposure: total portfolio exposure vs limit
      - Leverage: current leverage vs max
      - Drawdown: current drawdown vs threshold
      - Concentration: single-position concentration
      - Liquidity: liquidity score
      - Limits: position size limits
    """

    name: str = "RiskGate"
    config: RiskGateConfig = field(default_factory=RiskGateConfig)

    def check(self, context: TradingControlContext) -> ControlResult:
        """Evaluate all enabled risk checks."""
        if not context.risk_context:
            return self.fail_closed(context, "No risk context available")

        risk = context.risk_context
        violations = []

        # ── Exposure ────────────────────────────────────────────
        if self.config.enabled_checks.get("exposure", True):
            exposure = risk.get("exposure", 0.0)
            if exposure > self.config.max_exposure_pct:
                violations.append(
                    f"Exposure {exposure:.2%} > max {self.config.max_exposure_pct:.2%}"
                )

        # ── Leverage ────────────────────────────────────────────
        if self.config.enabled_checks.get("leverage", True):
            leverage = risk.get("leverage", risk.get("leverage_ratio", 1.0))
            if leverage > self.config.max_leverage:
                violations.append(
                    f"Leverage {leverage:.2f} > max {self.config.max_leverage:.2f}"
                )

        # ── Drawdown ────────────────────────────────────────────
        if self.config.enabled_checks.get("drawdown", True):
            drawdown = risk.get("drawdown", risk.get("portfolio_drawdown", 0.0))
            if drawdown > self.config.max_drawdown_pct:
                violations.append(
                    f"Drawdown {drawdown:.2%} > max {self.config.max_drawdown_pct:.2%}"
                )

        # ── Concentration ───────────────────────────────────────
        if self.config.enabled_checks.get("concentration", True):
            concentration = risk.get("concentration", risk.get("concentration_hhi", 0.0))
            if concentration > self.config.max_concentration_pct:
                violations.append(
                    f"Concentration {concentration:.2%} > max {self.config.max_concentration_pct:.2%}"
                )

        # ── Liquidity ───────────────────────────────────────────
        if self.config.enabled_checks.get("liquidity", True):
            liquidity = risk.get("liquidity", risk.get("liquidity_score", 1.0))
            if liquidity < self.config.min_liquidity_score:
                violations.append(
                    f"Liquidity {liquidity:.2f} < min {self.config.min_liquidity_score:.2f}"
                )

        # ── Position Size ───────────────────────────────────────
        if self.config.enabled_checks.get("position_size", True):
            pos_size = risk.get("position_size", risk.get("position_size_pct", 0.0))
            if pos_size > self.config.max_position_size_pct:
                violations.append(
                    f"Position size {pos_size:.2%} > max {self.config.max_position_size_pct:.2%}"
                )

        if violations:
            return self.reject_result(
                context,
                code="RISK_VIOLATION",
                reason="; ".join(violations),
            )

        return self.pass_result(context, reason="All risk checks passed")

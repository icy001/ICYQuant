"""
Greeks Risk Engine — Portfolio-level Greeks computation and monitoring.

Computes aggregate Delta, Gamma, Theta, Vega, and Rho for options
and derivatives positions. Supports Greek-based risk limits and
hedging recommendations.

Architecture::

    Options Positions → Delta/Gamma/Theta/Vega/Rho → Portfolio Greeks → Risk Limits
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GreeksSnapshot:
    """Portfolio-level Greeks at a point in time."""
    account_id: str
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    # Dollar-equivalent
    delta_dollar: float = 0.0
    gamma_dollar: float = 0.0

    # Normalized (per 1% move)
    delta_1pct: float = 0.0
    gamma_1pct: float = 0.0

    # Risk assessment
    greeks_risk_score: float = 0.0
    risk_level: str = "LOW"

    # Position-level breakdown
    by_symbol: dict[str, dict[str, float]] = field(default_factory=dict)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "delta_dollar": self.delta_dollar,
            "gamma_dollar": self.gamma_dollar,
            "delta_1pct": self.delta_1pct,
            "gamma_1pct": self.gamma_1pct,
            "greeks_risk_score": self.greeks_risk_score,
            "risk_level": self.risk_level,
            "by_symbol": {
                s: dict(g) for s, g in self.by_symbol.items()
            },
            "timestamp": self.timestamp.isoformat(),
        }


class GreeksRiskEngine:
    """
    Portfolio-level Greeks computation and monitoring engine.

    Aggregates Delta, Gamma, Theta, Vega, and Rho across all options
    and derivatives positions. Provides Greek-based risk limits and
    hedging recommendations.

    Usage::

        engine = GreeksRiskEngine()
        await engine.initialize()

        greeks = await engine.compute("ACC-01", positions)
        await engine.check_limits(greeks)
    """

    def __init__(
        self,
        max_delta: float = 100000.0,
        max_gamma: float = 10000.0,
        max_vega: float = 50000.0,
        max_theta: float = 10000.0,
    ) -> None:
        self._max_delta = max_delta
        self._max_gamma = max_gamma
        self._max_vega = max_vega
        self._max_theta = max_theta
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the Greeks engine."""
        self._initialized = True
        logger.info("GreeksRiskEngine initialized.")

    async def stop(self) -> None:
        """Stop the Greeks engine."""
        self._initialized = False
        logger.info("GreeksRiskEngine stopped.")

    # ---- Core API ----

    async def compute(
        self,
        account_id: str,
        positions: dict[str, dict[str, Any]],
        underlying_price: dict[str, float] = None,
    ) -> GreeksSnapshot:
        """
        Compute portfolio-level Greeks from positions.

        Each position dict should contain:
            - symbol, quantity, delta, gamma, theta, vega, rho, underlying
        """
        underlying_price = underlying_price or {}
        by_symbol: dict[str, dict[str, float]] = {}
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0
        delta_dollar = 0.0
        gamma_dollar = 0.0

        for symbol, pos in positions.items():
            qty = pos.get("quantity", 0)
            delta = pos.get("delta", 0) * qty
            gamma = pos.get("gamma", 0) * qty
            theta = pos.get("theta", 0) * qty
            vega = pos.get("vega", 0) * qty
            rho = pos.get("rho", 0) * qty

            total_delta += delta
            total_gamma += gamma
            total_theta += theta
            total_vega += vega
            total_rho += rho

            ul_price = underlying_price.get(pos.get("underlying", ""), 0)
            delta_dollar += delta * ul_price
            gamma_dollar += gamma * ul_price * ul_price * 0.01

            by_symbol[symbol] = {
                "delta": delta,
                "gamma": gamma,
                "theta": theta,
                "vega": vega,
                "rho": rho,
            }

        # Normalized
        delta_1pct = total_delta * 0.01
        gamma_1pct = total_gamma * 0.01

        # Risk score
        risk_score = self._compute_risk_score(total_delta, total_gamma, total_vega, total_theta)
        risk_level = "LOW"
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"

        return GreeksSnapshot(
            account_id=account_id,
            delta=total_delta,
            gamma=total_gamma,
            theta=total_theta,
            vega=total_vega,
            rho=total_rho,
            delta_dollar=delta_dollar,
            gamma_dollar=gamma_dollar,
            delta_1pct=delta_1pct,
            gamma_1pct=gamma_1pct,
            greeks_risk_score=risk_score,
            risk_level=risk_level,
            by_symbol=by_symbol,
        )

    async def check_limits(self, greeks: GreeksSnapshot) -> list[dict[str, Any]]:
        """Check Greeks against configured limits."""
        breaches = []

        if abs(greeks.delta) > self._max_delta:
            breaches.append({
                "greek": "delta",
                "value": greeks.delta,
                "limit": self._max_delta,
                "severity": "HIGH",
                "message": f"Portfolio Delta {greeks.delta:.0f} exceeds limit {self._max_delta:.0f}",
            })

        if abs(greeks.gamma) > self._max_gamma:
            breaches.append({
                "greek": "gamma",
                "value": greeks.gamma,
                "limit": self._max_gamma,
                "severity": "MEDIUM",
                "message": f"Portfolio Gamma {greeks.gamma:.0f} exceeds limit {self._max_gamma:.0f}",
            })

        if abs(greeks.vega) > self._max_vega:
            breaches.append({
                "greek": "vega",
                "value": greeks.vega,
                "limit": self._max_vega,
                "severity": "MEDIUM",
                "message": f"Portfolio Vega {greeks.vega:.0f} exceeds limit {self._max_vega:.0f}",
            })

        if abs(greeks.theta) > self._max_theta:
            breaches.append({
                "greek": "theta",
                "value": greeks.theta,
                "limit": self._max_theta,
                "severity": "LOW",
                "message": f"Portfolio Theta {greeks.theta:.0f} exceeds limit {self._max_theta:.0f}",
            })

        if breaches:
            logger.warning(f"Greeks limits breached: {len(breaches)} breaches")

        return breaches

    async def get_hedging_recommendation(
        self, greeks: GreeksSnapshot, target_delta: float = 0.0
    ) -> dict[str, Any]:
        """
        Generate hedging recommendation to reach target delta.

        Returns the delta-neutral hedge amount and direction.
        """
        delta_to_hedge = greeks.delta - target_delta

        if abs(delta_to_hedge) < 1.0:
            return {"action": "none", "message": "Delta within acceptable range"}

        action = "sell" if delta_to_hedge > 0 else "buy"
        return {
            "action": action,
            "delta_to_hedge": delta_to_hedge,
            "message": f"{action.upper()} {abs(delta_to_hedge):.0f} delta to reach target {target_delta}",
        }

    # ---- Internal ----

    def _compute_risk_score(
        self, delta: float, gamma: float, vega: float, theta: float
    ) -> float:
        """Compute weighted Greeks risk score."""
        score = 0.0

        # Delta: 40%
        if self._max_delta > 0:
            score += 40 * min(abs(delta) / self._max_delta, 1.0)

        # Gamma: 25%
        if self._max_gamma > 0:
            score += 25 * min(abs(gamma) / self._max_gamma, 1.0)

        # Vega: 20%
        if self._max_vega > 0:
            score += 20 * min(abs(vega) / self._max_vega, 1.0)

        # Theta: 15%
        if self._max_theta > 0:
            score += 15 * min(abs(theta) / self._max_theta, 1.0)

        return min(score, 100.0)

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        return {
            "max_delta": self._max_delta,
            "max_gamma": self._max_gamma,
            "max_vega": self._max_vega,
            "max_theta": self._max_theta,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
        }

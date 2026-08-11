"""
Risk Adapter — bridges Risk Engine into the integration control flow.

Commit 21 Part 1.1: translates risk check results into a normalized
risk_context dict consumed by RiskGate.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class RiskAdapter:
    """Bridges Risk Engine to integration layer.

    Domain (Risk) → Adapter → Integration Layer (RiskGate)
    """

    @staticmethod
    def build_risk_context(
        exposure: float = 0.0,
        leverage: float = 1.0,
        portfolio_drawdown: float = 0.0,
        concentration_hhi: float = 0.0,
        liquidity_score: float = 1.0,
        position_size_pct: float = 0.0,
        var_95: float = 0.0,
        var_99: float = 0.0,
        risk_budget_available: float = float("inf"),
        risk_budget_used: float = 0.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Build a risk context dict for integration gates."""
        return {
            "exposure": exposure,
            "leverage": leverage,
            "leverage_ratio": leverage,
            "drawdown": portfolio_drawdown,
            "portfolio_drawdown": portfolio_drawdown,
            "concentration": concentration_hhi,
            "concentration_hhi": concentration_hhi,
            "liquidity": liquidity_score,
            "liquidity_score": liquidity_score,
            "position_size": position_size_pct,
            "position_size_pct": position_size_pct,
            "var_95": var_95,
            "var_99": var_99,
            "risk_budget_available": risk_budget_available,
            "risk_budget_used": risk_budget_used,
            **kwargs,
        }

    @staticmethod
    def from_risk_check_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a risk check result dict to integration risk context."""
        return {
            "exposure": result.get("exposure", 0.0),
            "leverage": result.get("leverage", result.get("leverage_ratio", 1.0)),
            "leverage_ratio": result.get("leverage_ratio", result.get("leverage", 1.0)),
            "drawdown": result.get("drawdown", result.get("portfolio_drawdown", 0.0)),
            "portfolio_drawdown": result.get("portfolio_drawdown", result.get("drawdown", 0.0)),
            "concentration": result.get("concentration", result.get("concentration_hhi", 0.0)),
            "concentration_hhi": result.get("concentration_hhi", 0.0),
            "liquidity": result.get("liquidity", result.get("liquidity_score", 1.0)),
            "liquidity_score": result.get("liquidity_score", 1.0),
            "position_size": result.get("position_size_pct", result.get("position_size", 0.0)),
            "position_size_pct": result.get("position_size_pct", 0.0),
            "var_95": result.get("var_95", 0.0),
            "var_99": result.get("var_99", 0.0),
            "risk_budget_available": result.get("risk_budget_available", float("inf")),
            "risk_budget_used": result.get("risk_budget_used", 0.0),
            "passed": result.get("passed", result.get("authorized", False)),
            "rejection_reason": result.get("rejection_reason", result.get("reason", "")),
        }

    @staticmethod
    def normalize_risk_engine_result(risk_engine_result: Any) -> Dict[str, Any]:
        """Normalize a RiskEngine evaluation result."""
        if risk_engine_result is None:
            return {"passed": False, "reason": "No risk evaluation available"}
        if isinstance(risk_engine_result, dict):
            return risk_engine_result
        # Try common attribute access
        return {
            "passed": getattr(risk_engine_result, "passed", True),
            "exposure": getattr(risk_engine_result, "exposure", 0.0),
            "leverage": getattr(risk_engine_result, "leverage", 1.0),
            "drawdown": getattr(risk_engine_result, "drawdown", 0.0),
            "reason": getattr(risk_engine_result, "reason", ""),
        }

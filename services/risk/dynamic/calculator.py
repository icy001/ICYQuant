"""Dynamic Risk Calculator - VaR / CVaR computation engine."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import math


class RiskCalculator:
    """VaR / CVaR calculation engine.

    Supports:
    - Historical VaR
    - Parametric (variance-covariance) VaR
    - CVaR (Expected Shortfall)
    - Component VaR for position-level risk

    Key questions answered:
    - VaR: What is the maximum possible loss under normal conditions?
    - CVaR: What is the average loss in tail events?
    """

    # Z-scores for common confidence levels
    Z_SCORES = {
        0.90: 1.282,
        0.95: 1.645,
        0.975: 1.960,
        0.99: 2.326,
        0.995: 2.576,
        0.999: 3.090,
    }

    def __init__(self, default_confidence: float = 0.95):
        self.default_confidence = default_confidence

    def compute_var(
        self,
        returns: List[float],
        confidence: Optional[float] = None,
        method: str = "parametric",
        position_value: float = 1.0,
    ) -> Dict[str, float]:
        """Compute Value at Risk.

        Args:
            returns: Historical return series.
            confidence: Confidence level (default 0.95).
            method: "parametric" or "historical".
            position_value: Current position value.

        Returns:
            Dict with VaR metrics.
        """
        conf = confidence or self.default_confidence

        if method == "parametric":
            var_pct = self._parametric_var(returns, conf)
        elif method == "historical":
            var_pct = self._historical_var(returns, conf)
        else:
            raise ValueError(f"Unknown VaR method: {method}")

        var_amount = abs(var_pct) * position_value

        return {
            "method": method,
            "confidence": conf,
            "var_pct": round(var_pct, 6),
            "var_amount": round(var_amount, 2),
            "position_value": position_value,
        }

    def compute_var_multi_horizon(
        self,
        returns: List[float],
        horizons: List[int] = None,
        confidence: Optional[float] = None,
    ) -> Dict[str, float]:
        """Compute VaR for multiple time horizons.

        Args:
            returns: Daily return series.
            horizons: List of horizons in days.
            confidence: Confidence level.

        Returns:
            Dict with multi-horizon VaR.
        """
        if horizons is None:
            horizons = [1, 5, 10, 21]

        conf = confidence or self.default_confidence
        daily_var = self._parametric_var(returns, conf)
        daily_vol = self._compute_volatility(returns)

        results = {}
        for h in horizons:
            sqrt_h = math.sqrt(h)
            results[f"var_{h}d"] = round(daily_var * sqrt_h, 6)
            results[f"vol_{h}d"] = round(daily_vol * sqrt_h, 4)

        results["daily_var"] = round(daily_var, 6)
        results["daily_vol"] = round(daily_vol, 4)
        results["confidence"] = conf

        return results

    def compute_cvar(
        self,
        returns: List[float],
        confidence: Optional[float] = None,
        position_value: float = 1.0,
    ) -> Dict[str, float]:
        """Compute Conditional Value at Risk (Expected Shortfall).

        CVaR = Expected loss given loss exceeds VaR threshold.

        Args:
            returns: Historical return series.
            confidence: Confidence level.
            position_value: Current position value.

        Returns:
            Dict with CVaR metrics.
        """
        conf = confidence or self.default_confidence

        # Historical CVaR: average of returns worse than VaR threshold
        var_threshold = self._historical_var(returns, conf)
        tail_returns = [r for r in returns if r <= var_threshold]

        if tail_returns:
            cvar_pct = sum(tail_returns) / len(tail_returns)
        else:
            cvar_pct = var_threshold

        cvar_amount = abs(cvar_pct) * position_value

        return {
            "confidence": conf,
            "cvar_pct": round(cvar_pct, 6),
            "cvar_amount": round(cvar_amount, 2),
            "var_pct_at_threshold": round(var_threshold, 6),
            "tail_observations": len(tail_returns),
            "tail_avg_return": round(cvar_pct, 6),
            "position_value": position_value,
        }

    def compute_component_var(
        self,
        weights: List[float],
        volatilities: List[float],
        correlation_matrix: List[List[float]],
        confidence: Optional[float] = None,
        portfolio_value: float = 1.0,
    ) -> Dict[str, any]:
        """Compute component VaR for each position.

        Args:
            weights: Position weights in portfolio.
            volatilities: Individual asset volatilities.
            correlation_matrix: Asset correlation matrix.
            confidence: Confidence level.
            portfolio_value: Total portfolio value.

        Returns:
            Dict with component VaR decomposition.
        """
        conf = confidence or self.default_confidence
        z_score = self.Z_SCORES.get(conf, 1.645)
        n = len(weights)

        # Portfolio volatility
        portfolio_vol = self._portfolio_volatility(weights, volatilities, correlation_matrix)
        portfolio_var_pct = z_score * portfolio_vol
        portfolio_var = portfolio_var_pct * portfolio_value

        # Marginal VaR for each position
        component_vars = []
        for i in range(n):
            # Marginal contribution to portfolio volatility
            cov_sum = sum(weights[j] * volatilities[i] * volatilities[j] * correlation_matrix[i][j]
                          for j in range(n))
            marginal_vol = cov_sum / portfolio_vol if portfolio_vol > 0 else 0.0

            marginal_var = z_score * marginal_vol
            component_var = weights[i] * marginal_var * portfolio_value
            risk_contribution_pct = (component_var / portfolio_var * 100) if portfolio_var > 0 else 0.0

            component_vars.append({
                "index": i,
                "weight": weights[i],
                "marginal_var": round(marginal_var, 6),
                "component_var": round(component_var, 2),
                "risk_contribution_pct": round(risk_contribution_pct, 2),
            })

        return {
            "portfolio_volatility": round(portfolio_vol, 4),
            "portfolio_var": round(portfolio_var, 2),
            "portfolio_var_pct": round(portfolio_var_pct, 6),
            "confidence": conf,
            "components": component_vars,
            "diversification_ratio": self._diversification_ratio(weights, volatilities, portfolio_vol),
        }

    def compute_risk_metrics(
        self,
        returns: List[float],
        weights: Optional[List[float]] = None,
        volatilities: Optional[List[float]] = None,
        correlation_matrix: Optional[List[List[float]]] = None,
        position_values: Optional[List[float]] = None,
        total_value: float = 1.0,
    ) -> Dict[str, any]:
        """Compute comprehensive risk metrics for risk monitoring.

        Args:
            returns: Historical return series.
            weights: Asset weights.
            volatilities: Asset volatilities.
            correlation_matrix: Correlation matrix.
            position_values: Individual position values.
            total_value: Total portfolio value.

        Returns:
            Dict with full risk metrics.
        """
        vol = self._compute_volatility(returns)

        var_95 = self._parametric_var(returns, 0.95)
        var_99 = self._parametric_var(returns, 0.99)
        cvar_95 = self.compute_cvar(returns, 0.95, total_value)["cvar_pct"]
        cvar_99 = self.compute_cvar(returns, 0.99, total_value)["cvar_pct"]

        result = {
            "volatility": round(vol, 4),
            "var_95": round(var_95, 6),
            "var_99": round(var_99, 6),
            "cvar_95": round(cvar_95, 6),
            "cvar_99": round(cvar_99, 6),
            "var_95_amount": round(abs(var_95) * total_value, 2),
            "var_99_amount": round(abs(var_99) * total_value, 2),
            "cvar_95_amount": round(abs(cvar_95) * total_value, 2),
            "cvar_99_amount": round(abs(cvar_99) * total_value, 2),
            "annualized_volatility": round(vol * math.sqrt(252), 4),
        }

        if weights and volatilities and correlation_matrix:
            comp_var = self.compute_component_var(
                weights, volatilities, correlation_matrix,
                confidence=0.95, portfolio_value=total_value,
            )
            result["component_var"] = comp_var["components"]
            result["diversification_ratio"] = comp_var["diversification_ratio"]

        return result

    # ---- Internal computation helpers ----

    def _compute_volatility(self, returns: List[float]) -> float:
        """Compute standard deviation of returns."""
        if len(returns) < 2:
            return 0.0
        n = len(returns)
        mean = sum(returns) / n
        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        return math.sqrt(variance)

    def _parametric_var(self, returns: List[float], confidence: float) -> float:
        """Parametric VaR assuming normal distribution."""
        vol = self._compute_volatility(returns)
        mean = sum(returns) / max(len(returns), 1)
        z = self.Z_SCORES.get(confidence, 1.645)
        return mean - z * vol

    def _historical_var(self, returns: List[float], confidence: float) -> float:
        """Historical simulation VaR."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        idx = int((1.0 - confidence) * len(sorted_returns))
        idx = max(0, min(idx, len(sorted_returns) - 1))
        return sorted_returns[idx]

    def _portfolio_volatility(
        self,
        weights: List[float],
        volatilities: List[float],
        correlation_matrix: List[List[float]],
    ) -> float:
        """Compute portfolio volatility from weights and correlations."""
        n = len(weights)
        variance = 0.0
        for i in range(n):
            for j in range(n):
                variance += (weights[i] * weights[j] * volatilities[i] *
                             volatilities[j] * correlation_matrix[i][j])
        return math.sqrt(max(variance, 0.0))

    def _diversification_ratio(
        self,
        weights: List[float],
        volatilities: List[float],
        portfolio_vol: float,
    ) -> float:
        """Compute diversification ratio: weighted avg vol / portfolio vol."""
        if portfolio_vol <= 0:
            return 1.0
        weighted_avg = sum(w * v for w, v in zip(weights, volatilities))
        return weighted_avg / portfolio_vol

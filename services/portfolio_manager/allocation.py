"""Asset Allocation Engine – optimal capital distribution across assets."""

from typing import Dict, List, Optional


class AllocationEngine:
    """Allocates capital across assets based on alpha, risk, and constraints.

    Supports multiple allocation methods: equal-weight, alpha-weighted,
    risk-parity, and constrained optimization respecting position limits.
    """

    def __init__(
        self,
        max_single_position: float = 0.30,
        min_position: float = 0.02,
        cash_reserve: float = 0.05,
    ):
        self.max_single_position = max_single_position
        self.min_position = min_position
        self.cash_reserve = cash_reserve

    def allocate(
        self,
        assets: List[str],
        method: str = "equal",
        alpha_scores: Optional[Dict[str, float]] = None,
        risk_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Allocate capital across a list of asset symbols.

        Args:
            assets: List of asset symbols.
            method: Allocation method ("equal", "alpha", "risk_parity").
            alpha_scores: Per-asset alpha scores (0-1 scale).
            risk_scores: Per-asset risk scores (0-1 scale, lower = less risky).
        """
        if not assets:
            return {}

        if method == "equal":
            return self._equal_weight(assets)
        elif method == "alpha":
            return self._alpha_weight(assets, alpha_scores or {})
        elif method == "risk_parity":
            return self._risk_parity(assets, risk_scores or {})
        else:
            return self._equal_weight(assets)

    def _equal_weight(self, assets: List[str]) -> Dict[str, float]:
        """Equal-weight allocation respecting constraints."""
        investable = 1.0 - self.cash_reserve
        weight = investable / len(assets)
        # Cap at max single position
        weight = min(weight, self.max_single_position)
        return {asset: round(weight, 4) for asset in assets}

    def _alpha_weight(self, assets: List[str], alpha_scores: Dict[str, float]) -> Dict[str, float]:
        """Allocate proportional to alpha scores."""
        investable = 1.0 - self.cash_reserve

        # Fill missing scores with 0
        scores = {a: alpha_scores.get(a, 0.0) for a in assets}
        total_score = sum(scores.values())

        if total_score <= 0:
            return self._equal_weight(assets)

        weights: Dict[str, float] = {}
        for asset in assets:
            raw = investable * scores[asset] / total_score
            weights[asset] = round(min(raw, self.max_single_position), 4)

        # Re-normalize after capping
        w_total = sum(weights.values())
        if w_total > 0:
            for asset in weights:
                weights[asset] = round(weights[asset] / w_total * investable, 4)

        return weights

    def _risk_parity(self, assets: List[str], risk_scores: Dict[str, float]) -> Dict[str, float]:
        """Allocate inversely proportional to risk (risk parity)."""
        investable = 1.0 - self.cash_reserve

        # Convert risk to inverse: higher risk = lower weight
        inv_risk = {}
        for a in assets:
            risk = risk_scores.get(a, 0.5)
            # Avoid division by zero
            inv_risk[a] = 1.0 / max(risk, 0.01)

        total_inv = sum(inv_risk.values())

        weights: Dict[str, float] = {}
        for asset in assets:
            raw = investable * inv_risk[asset] / total_inv
            weights[asset] = round(min(raw, self.max_single_position), 4)

        return weights

    def optimize(
        self,
        assets: List[str],
        alpha_scores: Dict[str, float],
        risk_scores: Dict[str, float],
        alpha_weight: float = 0.5,
    ) -> Dict[str, float]:
        """Blended optimization: alpha + risk-adjusted allocation.

        Combines alpha-seeking and risk-avoidance into a single allocation.
        alpha_weight controls the balance (0 = pure risk parity, 1 = pure alpha).
        """
        investable = 1.0 - self.cash_reserve

        scores: Dict[str, float] = {}
        for a in assets:
            a_score = alpha_scores.get(a, 0.0)
            r_score = max(risk_scores.get(a, 0.5), 0.01)
            # Composite: alpha_weight * alpha + (1-alpha) * 1/risk
            composite = alpha_weight * a_score + (1 - alpha_weight) * (1.0 / r_score)
            scores[a] = max(composite, 0.001)

        total = sum(scores.values())

        weights: Dict[str, float] = {}
        for asset in assets:
            raw = investable * scores[asset] / total
            weights[asset] = round(min(raw, self.max_single_position), 4)

        return weights

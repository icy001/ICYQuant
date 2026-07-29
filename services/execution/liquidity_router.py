"""Liquidity-Aware Execution Router.

Bridges the Liquidity Engine with the Execution Optimizer.
Uses real-time liquidity analysis to adapt execution algorithm
selection, slicing parameters, and urgency levels.

Integrates:
    - Liquidity scoring → Algorithm selection
    - Market impact → Slice count optimization
    - Bid/Ask imbalance → Aggressiveness & urgency
    - Depth analysis → Max slice size constraint
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


class LiquidityRouter:
    """Routes execution decisions based on liquidity analysis.

    Consumes liquidity service output and produces adapted
    execution parameters for the Execution Optimizer.

    Usage:
        router = LiquidityRouter()
        params = router.adapt_execution(liquidity_eval_result)
        optimizer.optimize(task, market_state, **params)
    """

    def __init__(self) -> None:
        pass

    def adapt_execution(
        self,
        liquidity_result: Dict[str, Any],
        default_algorithm: str = "VWAP",
        default_slices: int = 10,
    ) -> Dict[str, Any]:
        """Adapt execution parameters based on liquidity.

        Args:
            liquidity_result: Output from LiquidityService.evaluate()
            default_algorithm: Fallback algorithm
            default_slices: Fallback slice count

        Returns:
            Dict with adapted: algorithm, slices, urgency, aggressiveness
        """
        score = liquidity_result.get("score", {})
        score_val = score.get("score", 50) if isinstance(score, dict) else 50
        grade = score.get("grade", "NORMAL") if isinstance(score, dict) else "NORMAL"
        impact = liquidity_result.get("impact", {})
        recommendation = liquidity_result.get("recommendation", {})
        imbalance = liquidity_result.get("imbalance", {})

        # 1. Algorithm selection based on liquidity grade
        algorithm = self._select_algorithm(grade, impact, recommendation, default_algorithm)

        # 2. Slice count based on impact and depth
        slices = self._determine_slices(grade, impact, default_slices)

        # 3. Urgency from imbalance
        urgency = recommendation.get("urgency", "NORMAL")

        # 4. Aggressiveness from imbalance
        aggressiveness = recommendation.get("aggressiveness", 0.5)

        # 5. Max slice size from depth analysis
        max_slice_size = self._determine_max_slice_size(liquidity_result)

        return {
            "algorithm": algorithm,
            "slices": slices,
            "urgency": urgency,
            "aggressiveness": aggressiveness,
            "max_slice_size": max_slice_size,
            "liquidity_grade": grade,
            "liquidity_score": score_val,
        }

    def _select_algorithm(
        self,
        grade: str,
        impact: Dict[str, Any],
        recommendation: Dict[str, Any],
        default_algorithm: str,
    ) -> str:
        """Select optimal execution algorithm based on liquidity.

        Imbalance-based recommendation takes priority when
        market is significantly directional.

        Rules:
            EXCELLENT → VWAP (confident, optimize timing)
            GOOD      → VWAP or TWAP
            NORMAL    → TWAP (balanced)
            POOR      → POV (control participation)
            AVOID     → POV with more slices (minimal impact)
        """
        # If recommendation explicitly suggests POV (imbalance-driven), respect it
        rec_algo = recommendation.get("recommended_algorithm", "")
        if rec_algo == "POV":
            return "POV"

        mapping = {
            "EXCELLENT": "VWAP",
            "GOOD": "VWAP",
            "NORMAL": "TWAP",
            "POOR": "POV",
            "AVOID": "POV",
        }
        return mapping.get(grade, default_algorithm)

    def _determine_slices(
        self,
        grade: str,
        impact: Dict[str, Any],
        default_slices: int,
    ) -> int:
        """Determine optimal slice count based on liquidity.

        Args:
            grade: Liquidity grade
            impact: Impact estimate dict
            default_slices: Default slice count

        Returns:
            Optimal slice count
        """
        recommended = impact.get("recommended_slices", default_slices)
        total_cost_bps = impact.get("total_cost_bps", 0)

        # Increase slices for poor liquidity
        if grade == "POOR" or grade == "AVOID":
            return max(recommended, 20, default_slices * 2)

        # Adjust for high impact
        if total_cost_bps > 30:
            return max(recommended, 15)

        return max(1, recommended)

    def _determine_max_slice_size(
        self,
        liquidity_result: Dict[str, Any],
    ) -> float:
        """Determine maximum safe slice size from depth.

        Args:
            liquidity_result: Liquidity evaluation result

        Returns:
            Max safe slice size in shares, or 0 for no limit
        """
        # Use volume_at_5bps as safe slice size
        depth_info = liquidity_result.get("depth", {})
        if isinstance(depth_info, dict) and "volume_at_5bps" in depth_info:
            return depth_info["volume_at_5bps"]

        return 0.0  # 0 means no explicit limit

    def get_routing_advice(
        self,
        liquidity_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get human-readable routing advice.

        Args:
            liquidity_result: Liquidity evaluation output

        Returns:
            Advice dict with recommendations and warnings
        """
        grade = (liquidity_result.get("score", {}).get("grade", "NORMAL")
                 if isinstance(liquidity_result.get("score"), dict) else "NORMAL")
        condition = (liquidity_result.get("imbalance", {}).get("condition", "BALANCED")
                     if isinstance(liquidity_result.get("imbalance"), dict) else "BALANCED")

        advice = {
            "NORMAL": "Standard execution conditions.",
            "HIGH": "Accelerate execution — favorable conditions.",
            "LOW": "Decelerate execution — wait for better conditions.",
            "CRITICAL": "Minimize market impact at all costs.",
        }

        warnings = []
        if grade in ("POOR", "AVOID"):
            warnings.append("Low liquidity — expect elevated impact costs.")
        if condition in ("EXTREME_BUY", "EXTREME_SELL"):
            warnings.append(f"Extreme {condition} pressure detected.")
        if grade == "AVOID":
            warnings.append("Consider splitting order over multiple days.")

        return {
            "liquidity_grade": grade,
            "market_condition": condition,
            "advice": advice.get(
                liquidity_result.get("recommendation", {}).get("urgency", "NORMAL"),
                "Proceed with standard execution.",
            ),
            "warnings": warnings,
        }

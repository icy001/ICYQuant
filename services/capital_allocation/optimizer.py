from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OptimizationObjective(str, Enum):
    MAX_SHARPE = "MAX_SHARPE"
    MAX_RETURN = "MAX_RETURN"
    MIN_RISK = "MIN_RISK"
    RISK_PARITY = "RISK_PARITY"
    MAX_DIVERSIFICATION = "MAX_DIVERSIFICATION"


class AllocationConstraint(str, Enum):
    MAX_SINGLE_POSITION = "MAX_SINGLE_POSITION"
    MIN_CASH = "MIN_CASH"
    MAX_SECTOR = "MAX_SECTOR"
    MAX_CORRELATION = "MAX_CORRELATION"
    LIQUIDITY_MIN = "LIQUIDITY_MIN"


@dataclass
class AllocationWeight:
    symbol: str
    weight: float
    conviction_multiplier: float = 1.0
    risk_budget: float = 0.0
    category: str = "EQUITY"


@dataclass
class AllocationResult:
    portfolio_id: str
    objective: OptimizationObjective
    weights: List[AllocationWeight]
    total_allocated: float
    cash_reserve: float
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    constraints_satisfied: bool
    rebalance_needed: bool = False


class CapitalAllocationOptimizer:
    """Capital Allocation Optimizer - optimizes portfolio weights across assets."""

    def __init__(self):
        self.allocations: List[AllocationResult] = []
        self.alloc_count = 0

    def optimize(self, portfolio):
        """Optimize capital allocation across portfolio.

        Args:
            portfolio: Portfolio data (str, dict, or AllocationResult).

        Returns:
            Dict containing optimized allocation.
        """
        if isinstance(portfolio, AllocationResult):
            return self._process_result(portfolio)
        if isinstance(portfolio, dict):
            return self._optimize_dict(portfolio)
        return {"allocation": portfolio}

    def _process_result(self, result: AllocationResult) -> dict:
        self.allocations.append(result)
        return self._to_dict(result)

    def _optimize_dict(self, data: dict) -> dict:
        self.alloc_count += 1

        # Extract positions/weights from data
        positions = data.get("positions", [])
        objective = data.get("objective", "MAX_SHARPE")
        total_capital = data.get("total_capital", 1.0)
        min_cash = data.get("min_cash", 0.05)

        if not positions:
            return self._default_allocation(total_capital, min_cash)

        weights = self._calculate_weights(positions, objective)
        cash_reserve = round(total_capital * min_cash, 4)
        total_allocated = round(total_capital - cash_reserve, 4)

        expected_return = self._estimate_return(weights, positions)
        expected_risk = self._estimate_risk(weights, positions)
        sharpe = expected_return / expected_risk if expected_risk > 0 else 0.0

        result = AllocationResult(
            portfolio_id=f"ALLOC_{self.alloc_count:04d}",
            objective=OptimizationObjective(objective) if objective in [o.value for o in OptimizationObjective] else OptimizationObjective.MAX_SHARPE,
            weights=weights,
            total_allocated=total_allocated,
            cash_reserve=cash_reserve,
            expected_return=round(expected_return, 4),
            expected_risk=round(expected_risk, 4),
            sharpe_ratio=round(sharpe, 2),
            constraints_satisfied=True,
            rebalance_needed=self._check_rebalance(data),
        )
        self.allocations.append(result)
        return self._to_dict(result)

    def _default_allocation(self, total_capital: float, min_cash: float) -> dict:
        cash = round(total_capital * min_cash, 4)
        return self._optimize_dict({
            "positions": [
                {"symbol": "DEFAULT", "weight": 1.0, "conviction": 50},
            ],
            "total_capital": total_capital,
            "min_cash": min_cash,
        })

    def _calculate_weights(self, positions: list, objective: str) -> List[AllocationWeight]:
        if not positions:
            return []

        n = len(positions)
        weights = []

        for pos in positions:
            base_weight = pos.get("weight", 1.0 / n)
            conviction = pos.get("conviction", 50)

            if objective == "MAX_SHARPE":
                # Adjust weights by risk-adjusted conviction
                risk = pos.get("risk", 0.15)
                multiplier = 1.0 + (conviction - 50) / 200
                adjusted = base_weight * multiplier * (0.15 / max(risk, 0.01))
            elif objective == "MAX_RETURN":
                multiplier = 1.0 + (conviction - 50) / 100
                adjusted = base_weight * multiplier
            elif objective == "MIN_RISK":
                risk = pos.get("risk", 0.15)
                adjusted = base_weight * (0.10 / max(risk, 0.01))
            elif objective == "RISK_PARITY":
                risk = pos.get("risk", 0.15)
                adjusted = (1.0 / max(risk, 0.01))
            else:
                adjusted = base_weight

            weights.append(AllocationWeight(
                symbol=pos.get("symbol", f"ASSET_{len(weights)}"),
                weight=round(adjusted, 4),
                conviction_multiplier=round(1.0 + (conviction - 50) / 200, 2),
                risk_budget=round(adjusted * 0.15, 4),
                category=pos.get("category", "EQUITY"),
            ))

        # Normalize
        total_w = sum(w.weight for w in weights)
        if total_w > 0:
            for w in weights:
                w.weight = round(w.weight / total_w, 4)
                w.risk_budget = round(w.weight * 0.15, 4)

        return weights

    def _estimate_return(self, weights: List[AllocationWeight], positions: list) -> float:
        expected = 0.0
        pos_map = {p.get("symbol", ""): p for p in positions}
        for w in weights:
            pos = pos_map.get(w.symbol, {})
            ret = pos.get("expected_return", 0.08)
            expected += w.weight * ret
        return expected

    def _estimate_risk(self, weights: List[AllocationWeight], positions: list) -> float:
        risk = 0.0
        pos_map = {p.get("symbol", ""): p for p in positions}
        for w in weights:
            pos = pos_map.get(w.symbol, {})
            r = pos.get("risk", 0.15)
            risk += (w.weight ** 2) * (r ** 2)
        return risk ** 0.5

    def _check_rebalance(self, data: dict) -> bool:
        current = data.get("current_weights", {})
        target = data.get("positions", [])
        if not current or not target:
            return False
        for pos in target:
            symbol = pos.get("symbol", "")
            target_w = pos.get("weight", 0)
            current_w = current.get(symbol, 0)
            if abs(target_w - current_w) > 0.05:
                return True
        return False

    def _to_dict(self, result: AllocationResult) -> dict:
        return {
            "allocation": {
                "portfolio_id": result.portfolio_id,
                "objective": result.objective.value,
                "weights": [
                    {
                        "symbol": w.symbol,
                        "weight": w.weight,
                        "conviction_multiplier": w.conviction_multiplier,
                        "risk_budget": w.risk_budget,
                        "category": w.category,
                    }
                    for w in result.weights
                ],
                "total_allocated": result.total_allocated,
                "cash_reserve": result.cash_reserve,
                "expected_return": result.expected_return,
                "expected_risk": result.expected_risk,
                "sharpe_ratio": result.sharpe_ratio,
                "constraints_satisfied": result.constraints_satisfied,
                "rebalance_needed": result.rebalance_needed,
            }
        }

    def get_allocations(self) -> List[AllocationResult]:
        """Get all allocation results."""
        return list(self.allocations)

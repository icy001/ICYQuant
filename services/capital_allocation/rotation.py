from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RotationAction(str, Enum):
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    MAINTAIN = "MAINTAIN"
    EXIT = "EXIT"
    ENTER = "ENTER"


class RotationSignal(str, Enum):
    MOMENTUM_UP = "MOMENTUM_UP"
    MOMENTUM_DOWN = "MOMENTUM_DOWN"
    THESIS_STRENGTHENING = "THESIS_STRENGTHENING"
    THESIS_WEAKENING = "THESIS_WEAKENING"
    RELATIVE_STRENGTH = "RELATIVE_STRENGTH"
    RELATIVE_WEAKNESS = "RELATIVE_WEAKNESS"
    REGIME_CHANGE = "REGIME_CHANGE"
    RISK_REBALANCE = "RISK_REBALANCE"


@dataclass
class RotationMove:
    symbol: str
    action: RotationAction
    from_weight: float
    to_weight: float
    delta: float
    signal: RotationSignal
    reason: str = ""


@dataclass
class RotationPlan:
    rotation_id: str
    moves: List[RotationMove]
    total_turnover: float
    urgency: str = "MEDIUM"
    capital_freed: float = 0.0
    capital_required: float = 0.0
    summary: str = ""


class CapitalRotationEngine:
    """Capital Rotation Engine - dynamically rotates capital between opportunities."""

    def __init__(self):
        self.rotations: List[RotationPlan] = []
        self.rot_count = 0

    def rotate(self, portfolio):
        """Generate capital rotation plan for portfolio.

        Args:
            portfolio: Portfolio data (str, dict, list, or RotationPlan).

        Returns:
            Dict containing rotation plan.
        """
        if isinstance(portfolio, RotationPlan):
            return self._process_rotation(portfolio)
        if isinstance(portfolio, dict):
            return self._rotate_dict(portfolio)
        if isinstance(portfolio, list):
            return self._rotate_positions(portfolio)
        return {"rotation": portfolio}

    def _process_rotation(self, plan: RotationPlan) -> dict:
        self.rotations.append(plan)
        return self._to_dict(plan)

    def _rotate_positions(self, positions: list) -> dict:
        self.rot_count += 1
        moves = []

        # Detect momentum and thesis changes
        for i, pos in enumerate(positions):
            if isinstance(pos, dict):
                move = self._analyze_position(pos)
                if move:
                    moves.append(move)

        # Calculate totals
        turnover = sum(abs(m.delta) for m in moves)
        capital_freed = sum(abs(m.delta) for m in moves if m.action in (RotationAction.DECREASE, RotationAction.EXIT))
        capital_required = sum(abs(m.delta) for m in moves if m.action in (RotationAction.INCREASE, RotationAction.ENTER))

        plan = RotationPlan(
            rotation_id=f"ROT_{self.rot_count:04d}",
            moves=moves,
            total_turnover=round(turnover, 4),
            capital_freed=round(capital_freed, 4),
            capital_required=round(capital_required, 4),
            summary=self._summarize(moves),
        )
        self.rotations.append(plan)
        return self._to_dict(plan)

    def _rotate_dict(self, data: dict) -> dict:
        positions = data.get("positions", data.get("portfolio", []))
        if not positions and "symbol" in data:
            positions = [data]
        return self._rotate_positions(positions)

    def _analyze_position(self, pos: dict) -> Optional[RotationMove]:
        symbol = pos.get("symbol", "UNKNOWN")
        current_weight = pos.get("current_weight", pos.get("weight", 0.05))
        target_weight = pos.get("target_weight", current_weight)
        momentum = pos.get("momentum", 0)
        thesis_strength = pos.get("thesis_strength", 0.5)
        conviction_delta = pos.get("conviction_delta", 0)

        delta = target_weight - current_weight

        if abs(delta) < 0.005:
            return None

        # Determine signal and action
        if delta > 0.03:
            signal = RotationSignal.THESIS_STRENGTHENING
            action = RotationAction.INCREASE
            reason = f"Thesis strengthening: conviction +{conviction_delta:.0%}"
        elif delta > 0:
            signal = RotationSignal.MOMENTUM_UP if momentum > 0 else RotationSignal.RELATIVE_STRENGTH
            action = RotationAction.INCREASE
            reason = f"Momentum positive (+{momentum:.0%})" if momentum > 0 else "Relative strength improving"
        elif delta < -0.03:
            signal = RotationSignal.THESIS_WEAKENING
            action = RotationAction.DECREASE if target_weight > 0 else RotationAction.EXIT
            reason = f"Thesis weakening: conviction {conviction_delta:.0%}"
        else:
            signal = RotationSignal.MOMENTUM_DOWN if momentum < 0 else RotationSignal.RISK_REBALANCE
            action = RotationAction.DECREASE
            reason = f"Momentum declining ({momentum:.0%})" if momentum < 0 else "Risk rebalance needed"

        return RotationMove(
            symbol=symbol,
            action=action,
            from_weight=round(current_weight, 4),
            to_weight=round(target_weight, 4),
            delta=round(delta, 4),
            signal=signal,
            reason=reason,
        )

    def _summarize(self, moves: List[RotationMove]) -> str:
        if not moves:
            return "No rotation needed - portfolio is balanced."
        increases = [m for m in moves if m.action in (RotationAction.INCREASE, RotationAction.ENTER)]
        decreases = [m for m in moves if m.action in (RotationAction.DECREASE, RotationAction.EXIT)]
        parts = []
        if increases:
            parts.append(f"Increase: {', '.join(f'{m.symbol}(+{m.delta:.1%})' for m in increases)}")
        if decreases:
            parts.append(f"Decrease: {', '.join(f'{m.symbol}({m.delta:.1%})' for m in decreases)}")
        return "; ".join(parts)

    def _to_dict(self, plan: RotationPlan) -> dict:
        return {
            "rotation": {
                "rotation_id": plan.rotation_id,
                "moves": [
                    {
                        "symbol": m.symbol,
                        "action": m.action.value,
                        "from_weight": m.from_weight,
                        "to_weight": m.to_weight,
                        "delta": m.delta,
                        "signal": m.signal.value,
                        "reason": m.reason,
                    }
                    for m in plan.moves
                ],
                "total_turnover": plan.total_turnover,
                "capital_freed": plan.capital_freed,
                "capital_required": plan.capital_required,
                "summary": plan.summary,
            }
        }

    def get_rotations(self) -> List[RotationPlan]:
        """Get all rotation plans."""
        return list(self.rotations)

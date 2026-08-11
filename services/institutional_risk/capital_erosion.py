"""CapitalErosion — model capital erosion in adverse scenarios.

Models sequential capital losses and estimates erosion rate,
remaining runway, and worst-case capital trajectory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ErosionStep:
    """A single step in the erosion path."""

    step: int
    capital: float
    loss: float
    loss_pct: float
    cumulative_loss_pct: float
    risk_budget_remaining: float


@dataclass
class ErosionResult:
    """Capital erosion analysis result."""

    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_erosion_pct: float = 0.0
    steps: List[ErosionStep] = field(default_factory=list)
    erosion_rate_per_step: float = 0.0
    steps_to_critical: int = 0
    risk_budget_exhausted_at_step: int = -1


class CapitalErosionModel:
    """Models sequential capital erosion.

    Simulates path-dependent capital erosion, where each loss
    reduces the remaining buffer and accelerates the crisis.

    Usage::

        model = CapitalErosionModel()
        result = model.simulate(
            capital=100_000_000,
            loss_per_sequence_pct=[2.0, 3.0, 5.0, 8.0, 10.0],
            risk_budget=8_000_000,
        )
        print(f"Capital after {len(result.steps)} steps: {result.final_capital:.0f}")
    """

    def __init__(self, critical_capital_ratio: float = 0.50):
        self._critical_ratio = critical_capital_ratio

    def simulate(
        self,
        capital: float,
        loss_per_sequence_pct: List[float],
        risk_budget: float = 0.0,
        risk_budget_consumption_per_step: Optional[List[float]] = None,
    ) -> ErosionResult:
        """Simulate capital erosion over a sequence of losses.

        Args:
            capital: initial capital
            loss_per_sequence_pct: sequential loss percentages
            risk_budget: total risk budget
            risk_budget_consumption_per_step: optional per-step consumption
        """
        current = capital
        risk_remaining = risk_budget
        steps: List[ErosionStep] = []
        critical_at = 0
        risk_exhausted_at = -1

        for i, loss_pct in enumerate(loss_per_sequence_pct):
            loss = current * (loss_pct / 100.0)
            current -= loss
            cumulative = (capital - current) / capital * 100

            # risk budget consumption
            if risk_budget_consumption_per_step and i < len(risk_budget_consumption_per_step):
                risk_remaining -= risk_budget_consumption_per_step[i]
            elif risk_budget > 0:
                risk_remaining -= loss * 0.1  # rough

            risk_remaining = max(0.0, risk_remaining)

            step = ErosionStep(
                step=i + 1,
                capital=current,
                loss=loss,
                loss_pct=loss_pct,
                cumulative_loss_pct=cumulative,
                risk_budget_remaining=risk_remaining,
            )
            steps.append(step)

            if current <= capital * self._critical_ratio and critical_at == 0:
                critical_at = i + 1

            if risk_remaining <= 0 and risk_exhausted_at == -1:
                risk_exhausted_at = i + 1

        erosion_rate = sum(s.loss_pct for s in steps) / max(len(steps), 1)

        return ErosionResult(
            initial_capital=capital,
            final_capital=current,
            total_erosion_pct=((capital - current) / capital * 100) if capital > 0 else 0,
            steps=steps,
            erosion_rate_per_step=erosion_rate,
            steps_to_critical=critical_at,
            risk_budget_exhausted_at_step=risk_exhausted_at,
        )

    def simulate_constant_rate(
        self,
        capital: float,
        daily_loss_pct: float,
        num_days: int,
        risk_budget: float = 0.0,
    ) -> ErosionResult:
        """Simulate erosion at a constant daily loss rate."""
        loss_sequence = [daily_loss_pct] * num_days
        return self.simulate(capital, loss_sequence, risk_budget)

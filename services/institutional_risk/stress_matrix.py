"""StressMatrix — multi-dimensional stress grid.

Computes a grid of stress scenarios:
    Market Shock × Volatility Shock × Liquidity Shock

Each cell contains P&L, VaR, ES, Drawdown, and Survival Score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.institutional_risk.stress_engine import (
    StressEngine,
    StressResult,
    StressScenario,
    StressScenarioType,
)


@dataclass
class StressMatrixCell:
    """A single cell in the stress matrix."""

    market_shock: float
    volatility_shock: float
    liquidity_shock: float
    portfolio_loss: float = 0.0
    loss_pct: float = 0.0
    survival_score: float = 100.0
    passed: bool = True


@dataclass
class StressMatrix:
    """Complete stress matrix."""

    name: str
    market_shocks: List[float] = field(default_factory=list)
    volatility_shocks: List[float] = field(default_factory=list)
    liquidity_shocks: List[float] = field(default_factory=list)
    cells: List[List[List[StressMatrixCell]]] = field(default_factory=list)
    worst_case: Optional[StressMatrixCell] = None
    worst_case_coords: Tuple[int, int, int] = (0, 0, 0)
    pass_rate: float = 0.0


class StressMatrixGenerator:
    """Generates multi-dimensional stress matrices.

    Creates a grid: Market × Vol × Liquidity and computes
    results for each cell, enabling heatmap-style analysis.

    Usage::

        gen = StressMatrixGenerator()
        matrix = gen.generate(
            capital=100_000_000,
            portfolio=...,
            market_shocks=[-5, -10, -20],
            vol_shocks=[20, 50, 100],
            liquidity_shocks=[-20, -50],
        )
        print(f"Worst case: {matrix.worst_case.loss_pct:.1f}%")
    """

    def __init__(self, stress_engine: Optional[StressEngine] = None):
        self._engine = stress_engine or StressEngine()

    def generate(
        self,
        name: str,
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        market_shocks: Optional[List[float]] = None,
        volatility_shocks: Optional[List[float]] = None,
        liquidity_shocks: Optional[List[float]] = None,
        current_risk: Optional[Dict[str, float]] = None,
    ) -> StressMatrix:
        """Generate a stress matrix.

        Args:
            name: matrix name
            capital: total capital
            portfolio_composition: portfolio to stress
            market_shocks: list of market shock percentages
            volatility_shocks: list of volatility shock percentages
            liquidity_shocks: list of liquidity shock percentages
            current_risk: current risk metrics
        """
        m_shocks = market_shocks or [-5.0, -10.0, -15.0, -20.0]
        v_shocks = volatility_shocks or [20.0, 50.0, 75.0, 100.0]
        l_shocks = liquidity_shocks or [-20.0, -30.0, -50.0]

        matrix = StressMatrix(
            name=name,
            market_shocks=m_shocks,
            volatility_shocks=v_shocks,
            liquidity_shocks=l_shocks,
        )

        worst_loss = 0.0
        worst_coords = (0, 0, 0)
        total_cells = 0
        passed_cells = 0

        cells: List[List[List[StressMatrixCell]]] = []

        for im, ms in enumerate(m_shocks):
            row: List[List[StressMatrixCell]] = []
            for iv, vs in enumerate(v_shocks):
                col: List[StressMatrixCell] = []
                for il, ls in enumerate(l_shocks):
                    scenario = StressScenario(
                        name=f"Matrix({ms},{vs},{ls})",
                        scenario_type=StressScenarioType.COMBINED,
                        market_shock_pct=ms,
                        volatility_shock_pct=vs,
                        liquidity_shock_pct=ls,
                    )

                    result = self._engine.run(
                        scenario, capital, portfolio_composition, current_risk
                    )

                    cell = StressMatrixCell(
                        market_shock=ms,
                        volatility_shock=vs,
                        liquidity_shock=ls,
                        portfolio_loss=result.portfolio_loss,
                        loss_pct=abs(result.portfolio_loss_pct),
                        survival_score=result.survival_score_under_stress,
                        passed=result.passed,
                    )
                    col.append(cell)

                    abs_loss = abs(result.portfolio_loss_pct)
                    if abs_loss > worst_loss:
                        worst_loss = abs_loss
                        worst_coords = (im, iv, il)

                    total_cells += 1
                    if result.passed:
                        passed_cells += 1

                row.append(col)
            cells.append(row)

        matrix.cells = cells
        matrix.worst_case_coords = worst_coords
        i, j, k = worst_coords
        matrix.worst_case = cells[i][j][k]
        matrix.pass_rate = passed_cells / max(total_cells, 1)

        return matrix

    def generate_2d(
        self,
        name: str,
        capital: float,
        portfolio_composition: Dict[str, Dict[str, Any]],
        x_shocks: List[float],
        y_shocks: List[float],
        x_label: str = "Market Shock",
        y_label: str = "Volatility Shock",
    ) -> StressMatrix:
        """Generate a 2D stress matrix (one dimension fixed)."""
        if y_label == "Volatility Shock":
            return self.generate(
                name=name,
                capital=capital,
                portfolio_composition=portfolio_composition,
                market_shocks=x_shocks,
                volatility_shocks=y_shocks,
                liquidity_shocks=[-30.0],  # fixed
            )
        # fallback to 3D with single element in third dim
        return self.generate(
            name=name,
            capital=capital,
            portfolio_composition=portfolio_composition,
            market_shocks=x_shocks,
            volatility_shocks=[50.0],
            liquidity_shocks=y_shocks,
        )

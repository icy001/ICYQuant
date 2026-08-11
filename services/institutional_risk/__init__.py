"""
Institutional Capital Risk & Stress Management

Commit 19 Part 1.4 — Capital Risk Aggregation, Stress Testing,
Liquidity Shock Simulation, and Portfolio Survival Controls.

Core Chain:
    Capital → Portfolio → Risk → Stress → Loss → Survival → Decision

Modules:
    - capital_risk_engine: main risk engine entry point
    - risk_aggregation: multi-level risk aggregation (strategy → capital pool)
    - var_engine: VaR computation (historical / parametric / Monte Carlo)
    - expected_shortfall: tail loss beyond VaR
    - drawdown_engine: drawdown tracking and recovery analysis
    - factor_risk: factor exposure, concentration, and shock simulation
    - correlation_risk: correlation breakdown, spike, and regime detection
    - tail_risk: tail event modeling, extreme loss, tail dependence
    - stress_engine: unified stress testing with scenario matrix
    - shocks: market, volatility, liquidity, correlation, spread, gap, execution
    - capital_survival: survival score, horizon, erosion, recovery capacity
    - risk_budget: budget allocation, monitoring, and breach handling
    - risk_action: deleveraging, reallocation, freeze, emergency liquidation
    - guards: risk guard, survival guard, stress guard
    - memory: risk memory, stress memory, survival memory
    - metrics, telemetry, diagnostics, health
"""

from services.institutional_risk.capital_risk_engine import CapitalRiskEngine
from services.institutional_risk.capital_risk_runtime import CapitalRiskRuntime
from services.institutional_risk.capital_risk_manager import CapitalRiskManager
from services.institutional_risk.capital_risk_controller import CapitalRiskController
from services.institutional_risk.capital_risk_orchestrator import CapitalRiskOrchestrator

__all__ = [
    "CapitalRiskEngine",
    "CapitalRiskRuntime",
    "CapitalRiskManager",
    "CapitalRiskController",
    "CapitalRiskOrchestrator",
]

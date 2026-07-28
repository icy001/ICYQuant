# AI Portfolio Manager Agent

## Responsibility

Upgrades ICYQuant from "providing trade recommendations" to "autonomously managing investment portfolios." Automates asset allocation, position sizing, strategy selection, rebalancing, and performance attribution based on market conditions, risk constraints, and investment objectives.

Key capabilities:

- **Asset Allocation** – Equal-weight, alpha-weighted, risk-parity, and blended optimization
- **Strategy Selection** – Multi-factor strategy scoring with category diversification
- **Portfolio Construction** – Constraints-aware weight optimization (position/sector/cash limits)
- **Dynamic Rebalancing** – Drift-triggered, signal/risk/regime-based rebalancing with turnover control
- **Performance Attribution** – Brinson-style decomposition (market beta + stock selection + factor exposure + sector allocation)
- **Investment Committee** – Simulated institutional approval workflow (Research → Risk → Vote → Decision)
- **Portfolio Memory** – Persistent allocation history with performance tracking

## Architecture

```
Investment Goal
  ↓
Portfolio Manager Agent
  ↓
Asset Allocation → Strategy Selection → Rebalancing
  ↓
Portfolio Optimization
  ↓
Execution Engine
```

## Modules

| Module | File | Purpose |
|--------|------|---------|
| PortfolioState | `manager.py` | Portfolio state and constraint model |
| PortfolioProposal | `manager.py` | Portfolio change proposal for approval |
| AllocationEngine | `allocation.py` | Multi-method asset allocation |
| StrategySelector | `strategy_selector.py` | Strategy scoring and selection |
| RebalanceEngine | `rebalance.py` | Drift correction and rebalance orders |
| PerformanceAttribution | `attribution.py` | Return decomposition |
| InvestmentCommittee | `committee.py` | Approval workflow simulation |
| PortfolioMemory | `memory.py` | Allocation history persistence |
| PortfolioManagerService | `service.py` | Unified service API |

## Usage

```python
from services.portfolio_manager import (
    PortfolioManagerService, Strategy,
)

service = PortfolioManagerService()

# Build a portfolio
weights = service.build_portfolio(
    portfolio_id="quant_fund_1",
    assets=["NVDA", "MSFT", "GOOGL", "TSLA"],
    objective="growth",
    method="alpha",
    alpha_scores={"NVDA": 0.9, "MSFT": 0.6, "GOOGL": 0.5, "TSLA": 0.3},
    risk_scores={"NVDA": 0.3, "MSFT": 0.2, "GOOGL": 0.25, "TSLA": 0.7},
)

# Select strategies
strategies = [
    Strategy(name="AI Momentum", category="momentum", sharpe=1.5),
    Strategy(name="Macro Hedge", category="macro", sharpe=1.2),
    Strategy(name="Mean Reversion", category="mean_reversion", sharpe=0.9),
]
selected = service.select_strategies(strategies)

# Rebalance
result = service.rebalance(
    current_weights={"NVDA": 0.30, "MSFT": 0.20, "CASH": 0.50},
    target_weights={"NVDA": 0.25, "MSFT": 0.25, "CASH": 0.50},
)

# Submit proposal for approval
approval = service.submit_proposal(
    portfolio_id="quant_fund_1",
    description="Increase NVDA allocation",
    current_weights={"NVDA": 0.20},
    proposed_weights={"NVDA": 0.25},
    rationale="Strong momentum signal",
    risk_score=25,
)

# Performance attribution
attribution = service.attribute_performance(
    total_return=0.15,
    market_return=0.05,
    stock_contributions={"NVDA": 0.06, "MSFT": 0.03},
    factor_contributions={"momentum": 0.03},
    sector_contributions={"tech": 0.02},
    period="Q2 2026",
)
```

## Allocation Methods

| Method | Description | Best For |
|--------|-------------|----------|
| `equal` | Equal weight across all assets | Passive / starting point |
| `alpha` | Proportional to alpha scores | High-conviction strategies |
| `risk_parity` | Inverse proportional to risk | Risk-focused portfolios |
| `optimize` | Blended alpha + risk-adjusted | Balanced active management |

## Investment Committee Workflow

```
AI Research Review → Risk Review → Committee Vote → Final Decision
       ↓                  ↓               ↓               ↓
  Alpha quality      Risk compliance   Composite       Approve/
  score (0-100)      score (0-100)     score          Reject(+conditions)
```

## Future Upgrade

Production Features:

- Reinforcement Learning Allocation (PPO/SAC-based agents)
- Black-Litterman Model (views-based allocation)
- Multi-Asset Optimization (equities + futures + FX + crypto)
- Autonomous Fund Management (zero human touch)
- Human Investment Committee Integration (collaborative workflow)
- Real-Time Drift Monitoring Dashboard
- Tax-Aware Rebalancing
- ESG/Responsible Investment Constraints

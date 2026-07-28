# AI Portfolio Intelligence Engine

## Overview

The Portfolio Intelligence Engine provides AI-driven portfolio management capabilities across
the full lifecycle: strategic allocation, position sizing, risk budgeting, exposure control,
optimization, rebalancing, performance attribution, and decision memory.

Part of ICYQuant v0.4.0-alpha1 (Commit 3 — Institutional Intelligence Layer).

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                PortfolioIntelligenceService                  │
│                    (Orchestrator)                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐  │
│   │Allocation│──▶│  Sizing  │──▶│Optimizer│──▶│  Budget  │  │
│   │  Engine  │   │  Engine  │   │ Engine  │   │  Engine  │  │
│   └─────────┘   └──────────┘   └─────────┘   └──────────┘  │
│        │              │              │               │       │
│        ▼              ▼              ▼               ▼       │
│   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐  │
│   │Exposure │──▶│ Rebalance│──▶│Attributor│──▶│ Memory  │  │
│   │ Engine  │   │  Engine  │   │  Engine  │   │ Engine  │  │
│   └─────────┘   └──────────┘   └──────────┘   └─────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Engine Pipeline

### 1. AssetAllocationEngine (`allocation.py`)

Strategic & tactical asset allocation across multiple strategies:

| Strategy | Description | Best For |
|----------|-------------|----------|
| EQUAL_WEIGHT | Uniform allocation | Quick benchmarks |
| MARKET_CAP | Market-cap weighted | Passive investing |
| RISK_PARITY | Inverse vol weighted | Risk-balanced portfolios |
| MIN_VARIANCE | Min vol (1/var) | Conservational portfolios |
| MOMENTUM_BASED | Trend-following weights | Tactical allocation |
| BLACK_LITTERMAN | Equilibrium + views | Conviction-based investing |
| ADAPTIVE | Multi-factor blend | Dynamic regime-aware |

**Key Data Models:**
- `AssetAllocation`: Single asset weight entry with drift tracking
- `AllocationResult`: Full allocation output with portfolio metrics
- `AssetClass`: 8 asset classes (EQUITY, FIXED_INCOME, COMMODITY, CASH, ALTERNATIVE, CRYPTO, REAL_ESTATE, PRIVATE_EQUITY)

### 2. PositionSizingEngine (`sizing.py`)

Risk-based position size calculation:

| Method | Formula | Parameters |
|--------|---------|------------|
| FIXED_FRACTION | Equal allocation | risk_per_trade |
| KELLY_CRITERION | f* = win - loss/ratio | kelly_fraction (half-Kelly) |
| VOLATILITY_TARGET | weights ∝ 1/vol | vol_target (15%) |
| EQUAL_RISK | Equal risk contribution | None |
| OPTIMAL_F | Max geometric growth | max_drawdown |
| RISK_BUDGET | Budgeted risk per asset | risk_budgets dict |

**Constraints applied:**
- Max position cap (default 25%)
- Max leverage cap (default 1.0x)
- Correlation penalty (>0.5 → up to 25% reduction)
- Liquidity adjustment (<0.5 score → size reduction)

### 3. RiskBudgetEngine (`budget.py`)

Hierarchical risk budget allocation across 5 levels:

```
Portfolio (100%) → Strategy (60%) → AssetClass (40%) → Sector (25%) → Position (10%)
```

**Status tracking:**
- `UNDER_BUDGET`: < 70% consumed
- `NORMAL`: 70–90% consumed
- `NEAR_LIMIT`: 90–100% consumed (warning)
- `EXCEEDED`: > 100% consumed (alert)

**Methods:** Equal, Volatility-Weighted, Sharpe-Weighted, Custom

### 4. ExposureEngine (`exposure.py`)

Multi-dimensional exposure monitoring across 9 dimensions:

| Dimension | Limit | Unit |
|-----------|-------|------|
| MARKET_BETA | 1.5 | beta |
| SECTOR | 30% | pct |
| GEOGRAPHY | 50% | pct |
| CURRENCY | 20% | pct |
| STYLE | 60% | pct |
| FACTOR | 40% | pct |
| INSTRUMENT | 40% | pct |
| LIQUIDITY | 30% | pct |
| CONCENTRATION | 15% | HHI |

### 5. PortfolioOptimizer (`optimizer.py`)

Multi-objective optimization with efficient frontier:

| Objective | Weight Selection |
|-----------|-----------------|
| MAX_SHARPE | weight ∝ excess_ret / var |
| MIN_VARIANCE | weight ∝ 1 / var |
| MAX_RETURN | All-in on highest return |
| RISK_PARITY | weight ∝ 1 / vol |
| TARGET_RISK | Scale max-Sharpe to target vol |
| TARGET_RETURN | Blend max-return and min-var |
| BLACK_LITTERMAN | Equilibrium + investor views |

**Features:**
- Efficient frontier computation (configurable points)
- Sensitivity analysis (marginal risk contributions)
- Constraint support (bounds, turnover, cardinality)

### 6. RebalanceEngine (`rebalance.py`)

Intelligent rebalancing with multiple strategies:

| Strategy | Trigger | Use Case |
|----------|---------|----------|
| THRESHOLD_BASED | Absolute drift > 5% | Automatic drift correction |
| CALENDAR_BASED | 90-day schedule + drift overlay | Regular maintenance |
| TACTICAL | Market signal + drift | Opportunity-driven |
| ADAPTIVE | Vol-regime adjusted thresholds | Dynamic markets |
| COST_OPTIMIZED | Benefit > Cost condition | Low-turnover portfolios |

**Trade generation:** Sells executed first (raise cash), then buys, sorted by size.

### 7. AttributionEngine (`attribution.py`)

Performance return decomposition:

| Method | Components |
|--------|------------|
| BRINSON | Allocation Effect, Selection Effect, Interaction Effect |
| FACTOR_BASED | Market, Size, Value, Momentum, Quality, Low Vol, Alpha |
| MULTI_LEVEL | Brinson at AssetClass + Sector + Security levels |
| TRANSACTION | Per-trade P&L + Transaction Costs |

### 8. PortfolioMemory (`memory.py`)

Decision history and analytics:

- **Events:** Records all portfolio decisions with outcomes and impact scores
- **Snapshots:** Periodic performance capture (returns, vol, Sharpe, drawdown)
- **Querying:** Filter by type, tag, outcome, date range
- **Knowledge Base:** Win rate, performance trends, actionable insights
- **Pruning:** Automatic removal of oldest events when exceeding max limit

## Usage

```python
from services.portfolio_intelligence import (
    PortfolioIntelligenceService,
    AssetClass,
)

service = PortfolioIntelligenceService()

# Full pipeline
result = service.build(
    asset_data={
        AssetClass.EQUITY: {"expected_return": 0.08, "volatility": 0.18},
        AssetClass.FIXED_INCOME: {"expected_return": 0.04, "volatility": 0.05},
        AssetClass.CASH: {"expected_return": 0.03, "volatility": 0.005},
    },
    current_weights={"equity": 0.55, "fixed_income": 0.25, "cash": 0.20},
)

print(f"Allocation: {result.allocation.to_dict()}")
print(f"Rebalance trades: {result.rebalance.trade_count}")
print(f"Healthy: {result.is_healthy}")
```

## Testing

```bash
pytest tests/portfolio_intelligence/test_portfolio_intelligence.py -v
```

## Future Upgrades

- Real CVXPY-based convex optimization
- Hierarchical Risk Parity (HRP) algorithm
- Bayesian regime-switching allocation
- Reinforcement learning for adaptive rebalancing
- Full Brinson-Fachler attribution (arithmetic vs geometric)
- Dynamic risk budgeting with rolling VaR/CVaR

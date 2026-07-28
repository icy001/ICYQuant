# Quant Decision Engine

## Responsibility

Provides:
- Signal Fusion
- Decision Scoring
- Strategy Ranking
- Risk Selection
- Approval Workflow

## Architecture

```
Signal → Decision Engine → Approval → Execution
```

## Modules

| Module | File | Purpose |
|--------|------|---------|
| Decision | `decision.py` | Decision model with full lifecycle (PENDING/APPROVED/REJECTED/EXECUTED) |
| SignalFusionEngine | `fusion.py` | Combines multiple signals (equal-weight, weighted, confidence-weighted) |
| DecisionScoringEngine | `scoring.py` | Score = Alpha + Model Confidence - Risk Penalty |
| StrategyRankingEngine | `ranking.py` | Ranks strategies by composite score or individual metrics |
| RiskAdjustedSelector | `selector.py` | Selects candidates considering risk-adjusted returns |
| ApprovalWorkflow | `approval.py` | Human-in-the-loop approval with auto-approve option |
| DecisionAudit | `audit.py` | Full audit trail recording why decisions were made |
| DecisionService | `service.py` | Orchestrates the full decision pipeline |

## Pipeline

```
Signal Generated
    ↓
Signal Fusion (SignalFusionEngine)
    ↓
Decision Scoring (DecisionScoringEngine)
    ↓
Risk Check (RiskAdjustedSelector)
    ↓
Strategy Ranking (StrategyRankingEngine)
    ↓
Approval (ApprovalWorkflow)
    ↓
Execution
    ↓
Audit (DecisionAudit)
```

## Scoring Formula

```
Decision Score = Alpha * α_weight + Model_Confidence * m_weight - Risk_Penalty * r_weight
```

## Decision Actions

| Score Range | Action |
|-------------|--------|
| > threshold | BUY |
| -threshold to +threshold | HOLD |
| < -threshold | SELL |

## Strategy Ranking Metrics

| Weight | Metric |
|--------|--------|
| 40% | Sharpe Ratio |
| 20% | Returns |
| 20% | Max Drawdown (inverted) |
| 20% | IC |

## Approval States

```
PENDING → APPROVED → EXECUTED
PENDING → REJECTED
```

## Future Upgrade

Production Features:
- Reinforcement Learning Decision
- Bayesian Decision Model
- Portfolio Aware Decision
- LLM Decision Explanation
- Automated Trading Approval

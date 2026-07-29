# AI Autonomous Research Scientist Engine

## Overview

The Research Scientist Engine transforms ICYQuant from an **AI Investment Organization** into an **AI Quant Research Laboratory** capable of continuously discovering new alpha sources.

## Architecture

```
              AI Autonomous Research Scientist Engine
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
Research Agent    Experiment Engine   Discovery Engine
      │                  │                  │
Hypothesis        Backtesting        Alpha Mining
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
              Research Knowledge Memory
```

## Core Modules

| Module | Class | Responsibility |
|---|---|---|
| `scientist.py` | `ResearchScientistAgent` | AI Research Scientist - initiates and manages research projects |
| `hypothesis.py` | `HypothesisGenerator` | Generates structured, testable hypotheses from ideas |
| `question.py` | `ResearchQuestionEngine` | Decomposes broad questions into verifiable components |
| `experiment.py` | `ExperimentDesignEngine` | Designs rigorous experiments (backtests, cross-val, simulations) |
| `data.py` | `DataInvestigationEngine` | Profiles and assesses data quality and characteristics |
| `discovery.py` | `QuantDiscoveryEngine` | Discovers alpha signals, factors, and patterns |
| `backtest.py` | `AutomaticBacktestingEngine` | Automatically backtests strategies with full metrics |
| `validation.py` | `ResearchValidationEngine` | Prevents overfitting, data leakage, and false alpha |
| `report.py` | `ResearchReportGenerator` | Auto-generates professional research reports |
| `memory.py` | `ResearchMemory` | Persistent knowledge repository (AI Quant Brain) |
| `service.py` | `ResearchScientistService` | Orchestrates the full autonomous research loop |

## Autonomous Research Loop

```
Question → Hypothesis → Experiment → Data → Discovery → Backtest → Validation → Report → Memory
```

### Stage Details

1. **Question Analysis**: Decompose broad questions into testable sub-questions
2. **Hypothesis Generation**: Produce structured hypotheses with null statements
3. **Experiment Design**: Select methodology, metrics, and success criteria
4. **Data Investigation**: Profile datasets for quality and anomalies
5. **Quant Discovery**: Mine factors, signals, and patterns from data
6. **Automatic Backtesting**: Compute Sharpe, drawdown, win rate, and attribution
7. **Research Validation**: Out-of-sample, walk-forward, Monte Carlo, bootstrap
8. **Report Generation**: Auto-generate research papers and strategy reports
9. **Memory Storage**: Save all findings to the AI Quant Brain

## Usage

```python
from services.research_scientist import ResearchScientistAgent, ResearchScientistService

# Create the research scientist
scientist = ResearchScientistAgent()

# Create the full service
service = ResearchScientistService(scientist)

# Run full research loop
result = service.run("Is AI CapEx driving semiconductor outperformance?")
print(result["summary"])

# Quick single hypothesis test
quick = service.quick_hypothesis_test("momentum factor in tech sector")
print(f"Sharpe: {quick['sharpe']}, Validation: {quick['validation']}")
```

## Hypothesis Types

| Type | Description | Test Method |
|---|---|---|
| MARKET | Macro/sector directional predictions | Regime analysis |
| FACTOR | Factor-return relationship | Fama-MacBeth regression |
| STRATEGY | Strategy performance predictions | Walk-forward backtest |
| RELATIONSHIP | Variable correlation | Pearson/Spearman |
| PATTERN | Chart/technical pattern | Conditional probability |
| CAUSAL | Cause-effect relationships | Granger causality |
| PREDICTIVE | ML-based predictions | Cross-validation |

## Validation Methods

- **Out-of-Sample Testing**: Prevents in-sample overfitting
- **Walk-Forward Analysis**: Tests temporal stability
- **Monte Carlo Simulation**: Assesses distribution of outcomes
- **Bootstrap**: Confidence intervals for metrics

## Key Metrics

| Metric | Description |
|---|---|
| Sharpe Ratio | Risk-adjusted return |
| Sortino Ratio | Downside risk-adjusted |
| Calmar Ratio | Drawdown-adjusted |
| Information Coefficient | Predictive power |
| Max Drawdown | Worst peak-to-trough |
| Win Rate | Percentage of profitable periods |
| Profit Factor | Gross profit / Gross loss |

## Research Domains

| Domain | Focus |
|---|---|
| MACRO | Monetary/fiscal policy, growth cycles |
| SECTOR | Revenue trends, competitive landscape |
| FACTOR | Momentum, value, quality, size |
| STRATEGY | Entry/exit signals, position sizing |
| RISK | Volatility, correlation, tail risk |
| PORTFOLIO | Allocation, rebalancing, diversification |
| EXECUTION | Market impact, timing, slippage |
| ALTERNATIVE | Sentiment, satellite, web scraping |
| CROSS_ASSET | Cross-asset relationships |
| MARKET_MICROSTRUCTURE | Order book, spread, depth |

## Future Upgrade

- AI Quant Scientist Team (multiple specialized scientists)
- Autonomous Factor Mining (systematic factor discovery)
- Neural Alpha Discovery (deep learning for alpha)
- Automated Academic Research (full paper generation)
- Self-Generating Trading Strategies (zero human input)
- Real-time Research Dashboard
- Cross-asset Alpha Transfer Learning

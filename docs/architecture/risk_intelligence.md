# AI Risk Intelligence Engine

## Responsibility

Upgrades traditional static risk controls into a dynamic, intelligent, and explainable risk management system. Uses AI to analyze market conditions, portfolio exposures, strategy states, and potential risks for early warning and risk optimization.

Key capabilities:

- **Dynamic Risk Assessment** – Multi-factor risk scoring with factor-level attribution
- **AI Risk Prediction** – Forward-looking risk forecasts using volatility momentum and market stress signals
- **Stress Testing** – Simulate extreme market scenarios with loss/drawdown/recovery projections
- **Scenario Simulation** – Institutional-grade scenario library (Market Crash, Liquidity Crisis, Sector Rotation, Volatility Spike, Macro Shock, etc.)
- **Risk Explanation** – Natural language explanations of risk drivers with actionable recommendations
- **Comprehensive Analysis** – Unified assessment + prediction + explanation + stress test pipeline

## Architecture

```
Portfolio
  ↓
AI Risk Intelligence Engine
  ↓
Risk Assessment → Scenario Analysis → Prediction
  ↓
Risk Decision
  ↓
Portfolio Adjustment
```

## Modules

| Module | File | Purpose |
|--------|------|---------|
| RiskProfile | `risk.py` | Core risk profile dataclass + scoring utilities |
| RiskAssessmentEngine | `assessment.py` | Multi-dimensional risk evaluation |
| RiskPredictionEngine | `prediction.py` | Forward risk forecasting |
| StressTestEngine | `stress_test.py` | Extreme scenario simulation |
| ScenarioSimulator | `scenario.py` | Scenario library management |
| RiskExplanationEngine | `explanation.py` | Natural language risk explanations |
| RiskIntelligenceService | `service.py` | High-level unified service API |

## Usage

```python
from services.risk_intelligence import RiskIntelligenceService

service = RiskIntelligenceService()

# Comprehensive analysis
analysis = service.comprehensive_analysis(
    portfolio_id="quant_fund_1",
    exposure=0.65,
    volatility=0.25,
    drawdown=0.12,
    concentration=0.35,
    beta=1.15,
    var_95=0.18,
    vol_momentum=0.3,
    correlation_regime=0.4,
    market_stress=0.3,
)

# Risk assessment only
profile = service.assess(
    portfolio_id="quant_fund_1",
    exposure=0.65,
    volatility=0.25,
    concentration=0.35,
)

# Risk prediction
prediction = service.predict(
    current_volatility=0.25,
    vol_momentum=0.3,
    correlation_regime=0.4,
    market_stress=0.3,
)

# Stress testing
results = service.stress_test_all(portfolio_value=5_000_000)
summary = service.stress_test_summary()
```

## Predefined Scenarios

| Scenario | Category | Price Shock | Recovery |
|----------|----------|-------------|----------|
| Market Crash | market_crash | -30% | ~120 days |
| Liquidity Crisis | liquidity | -15% | ~60 days |
| Sector Rotation | sector | -12% | ~21 days |
| Volatility Spike | volatility | -8% | ~21 days |
| Macro Shock | macro | -20% | ~60 days |
| Tech Correction | sector | -25% | ~60 days |
| Currency Shock | macro | -10% | ~21 days |

## Future Upgrade

Production Features:

- ML Risk Forecasting (LSTM/Transformer models)
- Full VaR / CVaR Engine with parametric and historical methods
- Monte Carlo Simulation with 10K+ paths
- Real-Time Risk Monitoring Dashboard
- AI Risk Agent with autonomous hedging decisions
- Multi-Asset Risk Aggregation
- Counterparty Risk Integration
- Regulatory Stress Testing (CCAR/DFAST compatible)

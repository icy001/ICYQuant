# AI Trading Copilot

## Responsibility

Provides an AI-powered assistant layer that connects ICYQuant's research, decision, risk, and execution capabilities to the trader's workflow.

Key capabilities:

- **Market Analysis** – Real-time multi-factor analysis with trend, risk level, and explanatory factors
- **Position Explanation** – Portfolio holdings commentary with strengths, risks, and concentration warnings
- **Risk Warning** – Continuous monitoring of exposure, drawdown, volatility, and concentration with critical/warning alerts
- **Trade Planning** – Signal-driven trade execution plans with entry, stop loss, target, and position sizing
- **Trade Review** – Post-trade quality assessment covering entry, exit, risk control, and improvement suggestions
- **Trading Memory** – Persistent record of trades, decisions, market context, and outcomes for long-term learning

## Architecture

```
Trader
  ↓
AI Copilot
  ↓
Quant Intelligence
  ↓
Decision Support
```

## Modules

| Module | File | Purpose |
|--------|------|---------|
| MarketAnalyst | `market_analysis.py` | Multi-factor market analysis |
| PositionAssistant | `position.py` | Position commentary & portfolio overview |
| RiskMonitor | `risk_alert.py` | Real-time risk monitoring & alerts |
| TradePlanner | `trade_plan.py` | Trade execution plan generation |
| TradeReviewer | `review.py` | Post-trade review & feedback |
| TradingMemory | `memory.py` | Trade history persistence & query |
| TradingCopilot | `copilot.py` | Central orchestration engine |
| TradingCopilotService | `service.py` | High-level service API |

## Usage

```python
from services.trading_copilot import TradingCopilotService

service = TradingCopilotService()

# Market analysis
analysis = service.analyze_market(
    symbol="NVDA",
    price_momentum=0.8,
    volume_confirmation=0.6,
    volatility=0.2,
    sector_strength=0.7,
)

# Risk monitoring
alerts = service.check_risks(
    exposure=0.85,
    drawdown=0.12,
    volatility=0.3,
    sector_concentration=0.55,
)

# Trade planning
plan = service.plan_trade(
    symbol="NVDA",
    current_price=100.0,
    signal=0.7,
    risk_limit=0.2,
)

# Trade review
review = service.review_trade(
    trade_id="T001",
    symbol="NVDA",
    entry_price=100.0,
    exit_price=115.0,
    take_profit=115.0,
)

# Memory
service.remember(
    trade_id="T001",
    symbol="NVDA",
    action="buy",
    decision_reason="momentum signal",
    outcome="win",
    pnl_pct=0.15,
)
```

## Future Upgrade

Production Features:

- LLM Conversation Layer (natural language interface)
- Real-Time Market Agent (streaming data integration)
- Voice Trading Assistant
- Broker Integration (direct order routing)
- Personalized Trading Memory (per-trader profiles)
- Autonomous Trade Monitoring (24/7 alerting)
- Multi-Asset Class Support (equities, futures, FX, crypto)

# AI Market Regime Intelligence Engine

## Responsibility

The Market Regime Intelligence Engine enables ICYQuant to understand current
market conditions and dynamically adapt strategy selection, risk exposure, and
portfolio allocation based on the detected regime.

Provides:

- Market State Model (trend + volatility + macro composite)
- Trend Detection (direction, strength, momentum)
- Volatility Analysis (VIX-based, historical vol, percentile)
- Macro Environment Analysis (growth, inflation, rates, credit)
- Regime Classification (fused multi-dimensional classification)
- Strategy Matching (regime → optimal strategy types)
- Adaptive Exposure Recommendations
- Regime Memory (history, transitions, patterns)

## Architecture

```
Market Data
    ↓
Feature Extraction (trend, volatility, macro)
    ↓
Trend Detector ──┐
Volatility Detector ──┼── Regime Classifier ──→ MarketRegime
Macro Analyzer ──┘
    ↓
Strategy Matcher (regime → strategies)
    ↓
Portfolio Adjustment (exposure, allocation)
    ↓
Regime Memory (history + learning)
```

## Module Structure

```
services/market_regime/
├── regime.py      - MarketRegime, RegimeState, RegimeTransition
├── trend.py       - TrendDetector
├── volatility.py  - VolatilityDetector
├── macro.py       - MacroAnalyzer
├── classifier.py  - RegimeClassifier (fuses all signals)
├── matcher.py     - StrategyMatcher (regime → strategy selection)
├── memory.py      - RegimeMemory, RegimeRecord
└── service.py     - MarketRegimeService (orchestrator)
```

## Key Concepts

### Market Regime States

Composite regimes are formed by fusing trend + volatility:

| Trend      | Low Vol       | High Vol       |
|------------|---------------|----------------|
| Bull       | BULL_LOW_VOL  | BULL_HIGH_VOL  |
| Bear       | BEAR_LOW_VOL  | BEAR_HIGH_VOL  |
| Sideways   | SIDEWAYS_LOW_VOL | SIDEWAYS_HIGH_VOL |

Special states: CRISIS, RISK_ON, RISK_OFF, FLIGHT_TO_QUALITY

### Strategy Matching

| Regime           | Recommended Strategies                  | Exposure |
|------------------|-----------------------------------------|----------|
| BULL_LOW_VOL     | momentum, growth, breakout              | 1.0      |
| BEAR_HIGH_VOL    | inverse, safe_haven, defensive          | 0.2      |
| SIDEWAYS         | mean_reversion, range_trading, neutral  | 0.6      |
| CRISIS           | safe_haven, tail_hedge, gold            | 0.1      |

### Confidence Scoring

```
Overall Confidence = trend_conf × 0.5 + vol_clarity × 0.3 + macro_conf × 0.2
```

## Usage

```python
from services.market_regime import MarketRegimeService

service = MarketRegimeService()

# Detect current regime
result = service.analyze_market({
    "price": 110, "ma_fast": 100, "ma_slow": 90,
    "vix": 14, "gdp_growth": 3.0, "inflation": 2.0,
})

print(f"Regime: {result['analysis']['summary']}")
print(f"Strategies: {result['recommendations']['strategies']}")
print(f"Exposure: {result['recommendations']['suggested_exposure']}")
```

## Future Upgrade

Production Features:

- Hidden Markov Model (HMM) regime detection
- Transformer-based market state model
- Reinforcement Learning for adaptive regime response
- Macro AI Agent for autonomous economic analysis
- Real-time regime prediction and early warning
- Multi-asset cross-market regime correlation
- Regime-conditional factor models
- Stress testing by historical regime scenarios

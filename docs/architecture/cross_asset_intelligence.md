# AI Cross Asset Intelligence Engine

## Overview

The Cross Asset Intelligence Engine establishes dynamic relationship models between global
assets, understands capital transmission paths across equities, bonds, currencies, commodities,
gold, and crypto, and converts cross-asset changes into trading signals, risk signals, and
asset allocation recommendations.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   CrossAssetIntelligenceService                   │
│                        (Pipeline Orchestrator)                    │
├──────────────────────────────────────────────────────────────────┤
│  Pipeline Steps:                                                  │
│    1. Equity-Bond Analysis     → yield/valuation signals          │
│    2. Dollar Intelligence      → USD cycle impacts                │
│    3. Commodity Intelligence   → macro condition signals          │
│    4. Crypto Intelligence      → risk appetite barometer          │
│    5. Correlation Analysis     → cross-asset relationships        │
│    6. Rotation Detection       → capital flow patterns            │
│    7. Signal Generation        → unified trading signals          │
│    8. Risk Assessment          → systemic risk evaluation         │
│    9. Memory Storage           → persistent history               │
└──────────────────────────────────────────────────────────────────┘
```

## Module Structure

### Data Models (`relationship.py`)

| Class | Description |
|-------|-------------|
| `AssetRelationship` | Pairwise asset correlation with type classification |
| `AssetNode` | Graph node representing an asset with its relationships |
| `RelationshipGraph` | Complete cross-asset relationship graph |
| `CrossAssetSignal` | Derived trading signal from cross-asset analysis |

| Enum | Members |
|------|---------|
| `AssetClass` | EQUITY, EQUITY_SECTOR, ..., CASH (18 members) |
| `RelationshipType` | STRONG_POSITIVE ... LEAD_LAG (10 members) |
| `RiskRegime` | RISK_ON, RISK_OFF, FLIGHT_TO_QUALITY, ..., NORMAL |
| `DollarTrend` | STRONG_APPRECIATION ... STRONG_DEPRECIATION (5) |

### Intelligence Engines

#### Equity-Bond Analyzer (`equity_bond.py`)

Analyzes yield curve, real yields, and credit spreads to assess:
- Equity market pressure from bond market conditions
- Growth stock vs value stock pressure (rate sensitivity)
- Valuation signals (OVERVAULED → CHEAP from bond perspective)

```python
analyzer = EquityBondAnalyzer()
result = analyzer.analyze_full(yield_10y=4.0, real_yield=1.0, credit_spread=1.0)
# → EquityBondResult(equity_pressure="NEUTRAL", valuation_signal="FAIR")
```

#### Dollar Intelligence (`dollar.py`)

Evaluates USD cycles and projects cross-asset impacts:
- Gold outlook (inverse relationship with USD)
- Commodity outlook (USD-denominated pricing)
- Emerging markets outlook (dollar debt sensitivity)
- Risk asset outlook (carry trade dynamics)

```python
engine = DollarIntelligenceEngine()
result = engine.analyze_full(dxy=95.0, real_yield=1.0, fed_stance="dovish")
# → DollarResult(trend=DEPRECIATION, gold_signal="bullish")
```

#### Commodity Intelligence (`commodity.py`)

Interprets commodity price signals for macro conditions:
- **Gold** → Risk-off/Inflation hedging demand
- **Copper** ("Dr. Copper") → Global industrial demand indicator
- **Oil** → Supply/demand balance, energy inflation
- **Natural Gas** → Seasonal demand and energy supply concerns

```python
engine = CommodityIntelligenceEngine()
gold = engine.analyze_gold(2100.0, dollar_trend="depreciation")
signal = engine.get_inflation_signal()  # "inflation_accelerating"
growth = engine.get_growth_signal()     # "growth_accelerating"
```

#### Crypto Intelligence (`crypto.py`)

Uses crypto as a leading indicator for risk appetite:
- BTC/ETH price action and trends
- BTC dominance cycles (BTC Season / Alt Season)
- Risk appetite classification for traditional markets

```python
engine = CryptoIntelligenceEngine()
result = engine.analyze_full(btc=60000, eth=3500, dominance=48.0)
# → risk_appetite=RISK_SEEKING, signal=BULLISH
```

### Analytical Engines

#### Correlation Engine (`correlation.py`)

Computes dynamic cross-asset correlations:
- **Methods**: Pearson, Spearman, Dynamic (exponentially weighted)
- **Analysis**: Rolling correlation, regime detection, matrix computation
- **Regime Detection**: NORMAL, CRISIS_CONVERGENCE (diversification failure), DECOUPLING, INVERSE

```python
engine = CorrelationEngine()
engine.add_prices({"SPX": 5000, "TLT": 95, "GLD": 200})
result = engine.analyze()
# → CorrelationResult(average_correlation=0.3, diversification_score=0.7)
```

#### Asset Rotation Detector (`rotation.py`)

Detects capital rotation patterns:
- **Risk-On/Risk-Off**: Equity vs bonds/gold rotation
- **Sector Rotation**: Cross-sector relative strength
- **Style Rotation**: Growth vs value dynamics
- **Flight to Safety**: Equity selling into bonds/gold

```python
detector = AssetRotationDetector()
detector.add_performance("SPX", 3.0)
detector.add_performance("TLT", -1.0)
event = detector.detect_risk_on_off()
# → RotationEvent(type=RISK_ON, strength=0.35)
```

### Decision Engines

#### Signal Generator (`signal.py`)

Synthesizes all sub-engines into unified signals:
- Weighted composite scoring from 7 signal sources
- Signal actions: OVERWEIGHT, MARKET_WEIGHT, UNDERWEIGHT, REDUCE, EXIT, HEDGE, MONITOR
- Priority levels: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL

#### Risk Monitor (`risk.py`)

Assesses systemic risk across 6 categories:
- **Volatility**: VIX-based stress measurement
- **Correlation**: Diversification failure detection
- **Liquidity**: Credit spreads and volume analysis
- **Currency**: Dollar strength impact on EM
- **Credit**: IG and HY spread stress
- **Tail Risk**: Options skew and VaR/CVaR

Risk levels: LOW → MODERATE → ELEVATED → HIGH → CRITICAL

### Infrastructure

#### Memory (`memory.py`)

Persistent analysis storage with:
- Type-indexed query (signal, risk, rotation, analysis)
- Tag-based retrieval
- Time-range queries with TTL-based expiration
- Automatic pruning at max_entries

## Usage Example

```python
from services.cross_asset_intelligence import CrossAssetIntelligenceService

service = CrossAssetIntelligenceService()

result = service.run_pipeline(
    yield_10y=4.0,
    real_yield=1.0,
    credit_spread=1.0,
    dxy=100.0,
    fed_stance="neutral",
    gold_price=2000.0,
    oil_price=80.0,
    copper_price=4.0,
    btc_price=50000,
    eth_price=3000,
    btc_dominance=50.0,
    vix=15.0,
)

# Trading signal
print(f"Signal: {result.signal.action.value}")
print(f"Score: {result.signal.score:.2f}")
print(f"Confidence: {result.signal.confidence:.2f}")

# Risk assessment
print(f"Risk: {result.risk.overall_level.value}")
print(f"Hedge: {result.risk.hedge_recommendation}")

# Allocation
allocation = result.allocation_advice
print(f"Suggested allocation: {allocation}")

# History
regime = service.get_current_regime()
summary = service.get_pipeline_summary(cycles=5)
```

## Test Coverage

- **170 tests** covering all modules
- Unit tests for all data models, enums, and properties
- Integration tests for full pipeline execution
- Bullish/bearish scenario testing
- Memory accumulation and lifecycle testing
- Correlation computation across multiple methods

# AI Macro Intelligence Engine

## Responsibility

Provides:
- Economic Cycle Detection
- Central Bank Policy Analysis
- Inflation Intelligence
- Liquidity Condition Monitoring
- Macro Event Impact Prediction
- Macro Regime Classification
- Strategy/Portfolio Adaptation

## Architecture

```
Global Macro Data
       │
       ▼
┌──────────────────────────────┐
│  AI Macro Intelligence Engine │
├──────────────────────────────┤
│  Economic Cycle  │ Inflation  │
│  Central Bank    │ Liquidity  │
│  Event Impact    │ Classifier │
├──────────────────────────────┤
│  Macro Strategy Adapter       │
└──────────────────────────────┘
       │
       ▼
Portfolio / Strategy Adjustment
```

## Modules

### Macro Data Model (`data.py`)
Core data structures for macro intelligence:
- `MacroIndicator` — Single economic data point with change/surprise calculation
- `MacroDataSnapshot` — Collection of indicators at a point in time
- `CentralBankEvent` — Central bank decision/communication
- `MacroEvent` — Scheduled macro event
- `MacroRegime` — Classified macro regime result
- `IndicatorCategory` — Growth, Employment, Inflation, Monetary, etc.
- `MacroRegimeState` — 10 composite regime states

### Economic Cycle Detector (`cycle.py`)
Detects economic cycle phase from multi-factor scoring:
- Growth momentum (GDP, PMI, production, retail)
- Employment momentum (NFP, unemployment, wages)
- Leading indicator momentum (LEI, yield curve, confidence)
- 9 cycle phases from DEEP_RECESSION to PEAK

### Central Bank Intelligence (`central_bank.py`)
Analyzes monetary policy stance:
- 9 major central banks (FED, ECB, BOJ, PBOC, BOE, RBA, RBNZ, BOC, SNB)
- Policy stance classification (AGGRESSIVE_HIKE to AGGRESSIVE_CUT)
- Hawkish-Dovish scale from statement keyword analysis
- Rate bias inference and next move probability estimation
- Policy theme and risk extraction from statements

### Inflation Analyzer (`inflation.py`)
Multi-dimensional inflation analysis:
- Headline and core inflation tracking
- Inflation momentum from component changes
- 8 trend classifications (RAPIDLY_RISING to DEFLATIONARY)
- 6 regime classifications (DISINFLATION to HYPERINFLATION)
- Target deviation and leading signal computation

### Liquidity Engine (`liquidity.py`)
Global liquidity condition monitoring:
- Monetary base (balance sheets, M2, reserves)
- Credit markets (HY/IG spreads, TED spread, lending)
- Currency conditions (DXY, EM FX, carry trade)
- Cross-border flows (global M2, capital flows)
- 7 liquidity conditions and 7 trend states
- Risk asset impact estimation

### Event Impact Predictor (`event.py`)
Macro event market impact prediction:
- 8 event categories (central bank, inflation, employment, etc.)
- Per-asset impact prediction with direction and magnitude
- Confidence intervals and risk warnings
- Historical pattern integration

### Macro Regime Classifier (`classifier.py`)
Fuses all intelligence signals into unified regime:
- Regime classification matrix (cycle × inflation × liquidity)
- Fuzzy matching for edge cases
- Aggregate risk and opportunity scores
- Asset allocation bias computation per regime

### Macro Strategy Adapter (`adapter.py`)
Translates macro regime to investment decisions:
- 12 strategy themes (growth, value, momentum, defensive, etc.)
- Regime → theme mapping with primary/secondary/avoid
- Asset exposure recommendations (equity, bonds, commodities, cash)
- Leverage and risk budget adjustments
- Sector rotation recommendations

### Service (`service.py`)
Orchestrates the complete pipeline:
- `analyze()` — Full pipeline with all components
- `analyze_simple()` — Quick analysis from dict
- `analyze_quick()` — Minimal-input rapid assessment
- Returns comprehensive `MacroIntelligenceReport`

## Macro Regime States

| Regime | Growth | Inflation | Liquidity | Risk Assets |
|--------|--------|-----------|-----------|-------------|
| GOLDILOCKS | ↑ | ↓ | Loose | Favorable |
| REFLATION | ↑ | ↑ early | Loose | Favorable |
| OVERHEATING | → | ↑↑ | Tightening | Cautious |
| STAGFLATION | ↓ | ↑ | Tight | Unfavorable |
| RECESSION | ↓ | ↓ | Tight | Unfavorable |
| RECOVERY | ↑ | ↓ | Easing | Favorable |
| EASING | → | → | Dovish | Favorable |
| TIGHTENING | → | → | Hawkish | Cautious |
| LIQUIDITY_SURGE | → | → | Extremely Loose | Very Favorable |
| LIQUIDITY_CRUNCH | → | → | Extremely Tight | Very Unfavorable |

## Usage

```python
from services.macro_intelligence import (
    MacroIntelligenceService,
    MacroDataSnapshot,
    MacroIndicator,
    CentralBankEvent,
    MacroEvent,
    IndicatorCategory,
)

service = MacroIntelligenceService()

# Build macro snapshot
snapshot = MacroDataSnapshot()
snapshot.add(MacroIndicator(name="GDP_Growth", value=4.0, category=IndicatorCategory.GROWTH))
snapshot.add(MacroIndicator(name="CPI", value=2.0, category=IndicatorCategory.INFLATION))
snapshot.add(MacroIndicator(name="M2_Growth", value=8.0, category=IndicatorCategory.MONETARY))
# ... add more indicators

# Add central bank events
fed = CentralBankEvent(
    bank="FED", event_type="decision",
    date=datetime.utcnow(), rate_change=0.0,
    current_rate=5.0, sentiment="dovish",
)

# Predict upcoming events
fomc = MacroEvent(name="FOMC Meeting", event_type="policy_meeting", importance=4)

# Run full analysis
report = service.analyze(snapshot, [fed], [fomc])

print(report.summary)
print(f"Equity exposure: {report.adaptation.equity_exposure:.0%}")
print(f"Themes: {[t.value for t in report.adaptation.primary_themes]}")
```

## Future Upgrade

Production Features:
- LLM Central Bank Speech Analysis (NLP on FOMC/ECB minutes)
- Macro Forecast Models (GDP/inflation nowcasting)
- Economic Scenario Simulation (Monte Carlo macro paths)
- Global Liquidity Prediction (real-time flow monitoring)
- AI Macro Research Agent (autonomous macro thesis generation)
- Cross-Asset Macro Factor Model
- Real-time Macro Surprise Index

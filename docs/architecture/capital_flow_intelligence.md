# AI Capital Flow Intelligence Engine

## Responsibility

Provides:

- Institutional Flow Detection
- Smart Money Tracking
- ETF Flow Analysis
- Options Flow Intelligence
- Liquidity Environment Prediction
- Capital Rotation Detection
- Flow Alpha Factor Generation
- Smart Money Knowledge Base

## Architecture

```
     ETF        Institutional    Options      Cross Asset
    Flow           Flow           Flow          Flow
      |             |             |             |
      +-------------+-------------+-------------+
                    |
                    v
        AI Capital Flow Intelligence Engine
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
  Institutional  Smart Money  Liquidity
    Detector      Tracker    Predictor
        |           |           |
        +-----------+-----------+
                    |
                    v
           Money Flow Signal
                    |
                    v
        Portfolio / Strategy Adjustment
```

## Key Data Models

| Model | Purpose |
|-------|---------|
| `CapitalFlowRecord` | Single capital flow data point from any source |
| `FlowEvent` | Significant capital movement event |
| `SectorRotation` | Sector-level capital migration |
| `FlowAlphaSignal` | Capital flow-derived alpha factor |

## Sub-Engines

### Institutional Flow Detector (`institutional.py`)
- 7 institutional behavior patterns: Accumulation, Distribution, Holding, Rotation In/Out, Hedging, Speculative
- Consecutive flow streak analysis
- Institutional confidence scoring
- Per-asset and aggregate analysis

### Smart Money Tracker (`smart_money.py`)
- 5 smart money actions: Entry, Exit, Adding, Reducing, Waiting
- Hedge fund, institutional, options, and dark pool flow analysis
- Entry/exit ratio monitoring
- Smart money trend detection

### ETF Flow Analyzer (`etf_flow.py`)
- 80+ ETF-to-sector mappings (semiconductor, technology, financial, healthcare, energy, etc.)
- Flow score normalization and streak tracking
- Sector rotation detection from ETF flows
- Aggregate sector flow mapping

### Options Flow Analyzer (`options_flow.py`)
- Call/put volume analysis
- Put/call ratio bias detection
- Large block trade identification (default $1M threshold)
- Gamma exposure estimation
- Unusual options activity detection

### Liquidity Predictor (`liquidity_predictor.py`)
- 5-component weighted index: Money Supply (25%), Bond Yield (20%), Dollar (20%), Credit Spread (20%), CB Policy (15%)
- 6 liquidity regimes: Abundant, Expanding, Neutral, Contracting, Tight, Crisis
- Risk asset outlook (favorable/cautious/unfavorable)
- Risk level computation

### Capital Rotation Engine (`rotation.py`)
- Cross-sector flow comparison
- Source-to-target rotation mapping
- Hottest/coldest sector identification
- Rotation strength and confidence scoring

### Flow Alpha Generator (`alpha.py`)
- 6 factor types: Institutional Flow, Smart Money, ETF Flow, Options Flow, Liquidity Environment, Composite
- Confidence-weighted signal aggregation
- Per-asset signal tracking

### Capital Flow Memory (`memory.py`)
- Flow observation storage with institutional behavior and smart money action
- Outcome recording for accuracy tracking
- Accuracy reports by behavior and smart money action
- Smart money win rate analysis
- Most reliable behavior identification

### Service Orchestration (`service.py`)
- Full pipeline: Collection → Institutional → Smart Money → ETF → Options → Liquidity → Rotation → Alpha → Memory
- Per-asset flow summary
- Market liquidity assessment
- Institutional activity snapshot
- Memory reporting

## Future Upgrade

Production Features:

- Real-Time Institutional Flow (13F filings, block trade feeds)
- Order Book Intelligence (level 2/3 data analysis)
- Dark Pool Analysis (ATS volume tracking)
- Fund Position Prediction (ML-based institutional positioning)
- Reinforcement Learning Flow Model (RL-optimized flow trading)
- Cross-border capital flow monitoring
- Central bank liquidity operation tracking
- Real-time capital flow dashboard with heat maps

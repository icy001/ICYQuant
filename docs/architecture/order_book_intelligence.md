# AI Order Book Intelligence Engine

## Overview

The Order Book Intelligence Engine provides real-time market microstructure analysis
for institutional-grade execution optimization. It decodes order book dynamics at
millisecond granularity to identify order flow imbalances, hidden liquidity, toxicity,
and generate microstructure alpha signals.

Part of ICYQuant v0.4.0-alpha1 (Commit 3 — Institutional Intelligence Layer).

## Architecture

```
Exchange Feed
    ↓
OrderBookBuilder ─────── OrderBookSnapshot (L1/L2/L3)
    ↓
┌─────────────────────────────────────────────────────────┐
│              OrderBookIntelligenceService                │
├─────────────────────────────────────────────────────────┤
│  OrderImbalanceAnalyzer    LiquidityWallDetector         │
│  HiddenLiquidityEstimator  IcebergDetector              │
│  LargeOrderTracker         OrderFlowToxicityAnalyzer    │
│  QueuePositionEstimator    MicrostructureAlphaGenerator │
│  OrderBookMemory                                        │
└─────────────────────────────────────────────────────────┘
    ↓
Execution Engine ← Alpha Signal / Queue Position / Toxicity Advice
```

## Modules

### 1. OrderBookBuilder (`snapshot.py`)

Maintains real-time Level 1/2/3 order book state from streaming events.

| Feature | Description |
|---------|-------------|
| `update(side, price, volume, event)` | Process ADD/MODIFY/CANCEL/EXECUTE events |
| `apply_snapshot(bids, asks)` | Replace book with full snapshot |
| `snapshot()` | Generate current `OrderBookSnapshot` |
| Pruning | Auto-prunes to max_levels and max_history |

**OrderBookSnapshot properties:** best_bid, best_ask, mid_price, spread, spread_bps,
bid_volume_total, ask_volume_total, depth_at(), weighted_price(), imbalance(), to_dict()

### 2. OrderImbalanceAnalyzer (`imbalance.py`)

Real-time bid/ask imbalance with multi-method calculation:

| Method | Weighting |
|--------|-----------|
| SIMPLE | (bid - ask) / total |
| VOLUME_WEIGHTED | Weighted by distance from mid |
| DEPTH_WEIGHTED | Weighted by level depth (1/n) |
| MULTI_LEVEL | Composite blend (40/35/25) |

**Output:** `ImbalanceSignal` with score (-1 to +1), direction (STRONG_BUY→STRONG_SELL),
confidence, and trend analysis.

### 3. LiquidityWallDetector (`liquidity_wall.py`)

Detects significant resting orders that act as support/resistance:

| Strength | Multiplier | Typical Use |
|----------|-----------|-------------|
| MINOR | 2× avg | Caution zone |
| MODERATE | 5× avg | Potential support/resistance |
| MAJOR | 10× avg | Strong S/R zone |
| FORTRESS | 20× avg | Hard barrier |

Features: wall persistence tracking, dominant side detection, support/resistance zone
prediction.

### 4. HiddenLiquidityEstimator (`hidden_liquidity.py`)

Estimates dark pool / hidden / iceberg volume from visible trade patterns:

**Detection indicators:**
- Repeated fills at same price without visible order change
- Trades occurring mid-spread
- Large trades with minimal price impact
- Order book replenishment after fills
- Midpoint trade clusters
- Regular time-pattern fills

**Output:** `HiddenLiquidityEstimate` with probability, estimated volume, buy/sell
ratios, and dark pool activity level.

### 5. IcebergDetector (`iceberg.py`)

Identifies iceberg orders by monitoring repeated fills at same price with constant
display size replenishment.

| Status | Criteria |
|--------|----------|
| NONE | No pattern detected |
| SUSPECTED | 2+ consistent fills |
| CONFIRMED | 3+ fills with >70% confidence |
| DISSOLVED | Pattern disappeared |

Tracks display size consistency, replenishment intervals, and hidden ratio.

### 6. LargeOrderTracker (`large_order.py`)

Tracks institutional block orders, sweeps, and aggressive execution:

| Category | Detection Criteria |
|----------|-------------------|
| INSTITUTIONAL_BLOCK | Notional > block_threshold ($100k) |
| SWEEP | Consumed ≥ 3 price levels |
| AGGRESSIVE_BUY/SELL | Taker-initiated trades |
| ACCUMULATION/DISTRIBUTION | Gradual directional flow |

**Output:** `InstitutionActivity` with activity level (LOW→EXTREME), net flow,
accumulation score, and per-order tracking.

### 7. OrderFlowToxicityAnalyzer (`toxicity.py`)

VPIN-based (Volume-synchronized Probability of Informed Trading) toxicity:

| Toxicity | VPIN Range | Execution Strategy |
|----------|-----------|-------------------|
| LOW | <0.3 | Aggressive (30% participation) |
| MODERATE | 0.3–0.5 | Balanced (15% participation) |
| HIGH | 0.5–0.7 | Passive (5% participation) |
| EXTREME | >0.7 | Defensive (1% participation) |

### 8. QueuePositionEstimator (`queue.py`)

Predicts fill probability and estimated time-to-fill for limit orders:

| Position | Queue Progress | Fill Probability |
|----------|---------------|-----------------|
| FRONT | 0–10% | Very High / High |
| MIDDLE | 10–70% | Moderate |
| BACK | 70–100% | Low / Very Low |

Execution style recommendation: PASSIVE / OPPORTUNISTIC / AGGRESSIVE

### 9. MicrostructureAlphaGenerator (`alpha.py`)

Synthesizes alpha from all microstructure components:

| Component | Weight | Signal |
|-----------|--------|--------|
| Imbalance | 35% | Directional momentum |
| Liquidity Wall | 15% | Breakout/reversal |
| Toxicity | -20% | Inverted signal |
| Iceberg | 15% | Institutional flow |
| Hidden Liquidity | 10% | Liquidity premium |
| Institutional Flow | 5% | Net flow |

**Output:** `MicroAlphaSignal` with alpha_score (-1 to +1), direction (LONG/SHORT/FLAT),
strength (WEAK→VERY_STRONG), confidence, and expected horizon.

### 10. OrderBookMemory (`memory.py`)

Records microstructure events, tracks alpha accuracy, builds knowledge base:

- Event recording with type/symbol/price tagging
- Alpha signal verification (confirmed/failed)
- Knowledge base: event distribution, accuracy stats, wall price clustering
- Querying: by type, price range, recency

## Usage

```python
from services.order_book_intelligence import (
    OrderBookIntelligenceService,
    OrderBookBuilder,
    BookSide,
)

service = OrderBookIntelligenceService()
builder = OrderBookBuilder(symbol="AAPL")

# Feed order book
builder.apply_snapshot(
    bids={150.0: 5000, 149.5: 10000},
    asks={150.5: 3000, 151.0: 5000},
)

# Full analysis
report = service.analyze_snapshot(builder.snapshot())

print(f"Imbalance: {report.imbalance.direction.value} ({report.imbalance.score:.4f})")
print(f"Alpha: {report.alpha.direction.value} ({report.alpha.alpha_score:.4f})")
print(f"Toxicity: {report.toxicity.toxicity_level.value}")
```

## Testing

```bash
pytest tests/order_book_intelligence/test_order_book.py -v
```

## Future Upgrades

- Full Level-3 order book (individual order tracking)
- VPIN real-time streaming engine
- Smart order routing with exchange selection
- Adaptive execution with reinforcement learning
- Cross-venue microstructure arbitrage
- Real-time market regime classification from microstructure

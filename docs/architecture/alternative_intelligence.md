# AI Alternative Data Intelligence Engine

## Responsibility

Provides:
- News Intelligence (sentiment, sector classification, entity extraction)
- Social Sentiment Analysis (platform sentiment, buzz detection, contrarian signals)
- Web Intelligence (traffic, search trends, hiring data, app downloads)
- Satellite Intelligence (factory activity, port traffic, energy consumption)
- Alternative Alpha Discovery (feature → alpha candidate transformation)
- Multi-Source Data Fusion (price + macro + alternative alpha combination)
- Alternative Memory (historical storage, similarity search, performance tracking)

## Architecture

```
Alternative Data Sources
    │
    ├── News ──────────→ NewsIntelligence ──→ Sentiment + Sectors + Entities
    │
    ├── Social ────────→ SocialSentimentEngine ──→ Buzz + Polarity + Contrarian
    │
    ├── Web ───────────→ WebIntelligenceEngine ──→ Growth + Momentum + Profile
    │
    ├── Satellite ─────→ SatelliteIntelligenceEngine ──→ Activity + Sector Signals
    │
    └── Other ─────────→ Collector ──→ Unified AlternativeRecord
                                │
                                ▼
                    AlternativeFeature Extraction
                                │
                                ▼
                    AlternativeAlphaDiscovery
                                │
                                ▼
                    AlternativeDataFusion
                    (Price + Macro + Alternative)
                                │
                                ▼
                    Alpha Research Engine
```

## Key Data Models

| Model | Purpose |
|-------|---------|
| `AlternativeRecord` | Atomic ingested record from any alternative source |
| `AlternativeFeature` | Engineered feature ready for alpha discovery |
| `AlphaCandidate` | Candidate alpha signal with confidence & IC |
| `FusionResult` | Combined price+macro+alternative alpha per asset |
| `MemoryEntry` | Persisted analysis with performance tracking |

## Sub-Engines

### News Intelligence
- 8 sector classifications (AI semiconductor, cloud, fintech, biotech, energy, consumer, real estate, automotive)
- Keyword-based sentiment scoring with confidence estimation
- Impact magnitude assessment (0-1)
- Entity extraction (ticker patterns)
- Feature generation for alpha pipeline

### Social Sentiment Engine
- Multi-platform sentiment scoring (-1 to 1)
- Volume surge detection (viral/trending indicators)
- Buzz score from engagement + intensity + caps ratio
- Asset-level sentiment aggregation
- Contrarian signal detection (extreme sentiment → reversal)
- Trending topic extraction

### Web Intelligence Engine
- 8 metric types (traffic, search trends, product rank, hiring, app downloads, page views, bounce rate, time on site)
- Directional signal classification (up/down/neutral)
- Asset-level web profile with composite growth score
- Growth momentum detection (accelerating/decelerating/stable)
- Growth leader ranking

### Satellite Intelligence Engine
- 6 observation types (factory activity, port traffic, energy consumption, parking lot, construction, agriculture)
- Activity level classification (low/moderate/high)
- Sector-to-observation mapping (semiconductor → factory activity, retail → parking lot, etc.)
- Location-level composite activity profiles
- Sector signal generation (BULLISH/BEARISH/NEUTRAL)

### Alternative Alpha Discovery
- Feature-to-candidate transformation with category weights
- Sigmoid z-score normalization
- Signal strength → confidence mapping
- Decay half-life estimation by category
- Asset-level alpha aggregation
- Top asset ranking

### Data Fusion Engine
- Regime-dependent weighting (trending, high_volatility, low_volatility, event_driven)
- Correlation penalty for overlapping signals
- Multi-source alpha combination
- Confidence aggregation
- Per-asset fusion history

### Alternative Memory
- Store with multi-index (source, asset, metadata tags)
- Similarity search via Jaccard token overlap
- Performance tracking (realized alpha)
- Retrieval count statistics
- Best/worst performing entry queries

## Future Upgrade

Production Features:
- LLM News Agent (GPT/Claude-based news analysis)
- Real-Time Social Monitoring (Twitter/X, Reddit, StockTwits streaming)
- Satellite ML Models (CNN-based activity detection from imagery)
- Supply Chain Intelligence (supplier network analysis, shipment tracking)
- Alternative Data Marketplace Integration (Bloomberg ALT, Neudata, Eagle Alpha)
- NLP Entity Extraction with NER models
- Real-time Web Scraping Pipeline
- Alternative Factor Backtesting Framework

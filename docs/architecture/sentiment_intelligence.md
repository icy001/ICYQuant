# AI Sentiment Intelligence Engine

## Responsibility

Provides:

- Market Emotion Detection
- NLP Sentiment Analysis
- Fear & Greed Modeling
- Sentiment Momentum Tracking
- Price-Sentiment Divergence Detection
- Sentiment Alpha Factor Generation
- Market Psychology Memory

## Architecture

```
     News       Social       Trading      Options
       |            |            |            |
       +------------+------------+------------+
                    |
                    v
          AI Sentiment Intelligence Engine
                    |
        +-----------+-----------+
        |           |           |
        v           v           v
      NLP     Emotion     Fear/Greed
        |           |           |
        +-----------+-----------+
                    |
                    v
          Sentiment Factor Generation
                    |
                    v
          Alpha / Risk Adjustment
```

## Key Data Models

| Model | Purpose |
|-------|---------|
| `SentimentRecord` | Raw sentiment data point from any source |
| `SentimentEvent` | Significant sentiment event detected in market |
| `SentimentDivergence` | Price-sentiment divergence signal |
| `SentimentAlphaSignal` | Sentiment-derived alpha factor |

## Sub-Engines

### NLP Analyzer (`nlp.py`)
- Lexicon-based financial text sentiment analysis
- Bullish/bearish keyword detection with 50+ financial terms
- Negation and intensifier handling
- Financial event extraction (earnings, M&A, IPO, etc.)
- Entity recognition with ticker and company name detection

### Emotion Detector (`emotion.py`)
- 10 market emotion states: Euphoria, Optimism, Hope, Neutral, Anxiety, Fear, Panic, Capitulation, Despair, Relief
- State transition tracking
- Emotion intensity and confidence scoring
- Sentiment trend analysis
- Extreme risk level computation

### Fear & Greed Model (`fear_greed.py`)
- 5-component weighted index: Volatility (25%), Put/Call (20%), Momentum (20%), Fund Flow (20%), Social (15%)
- 5 zones: Extreme Fear, Fear, Neutral, Greed, Extreme Greed
- Contrarian signal generation (buy at extreme fear, sell at extreme greed)
- Position size risk adjustment factors
- Score momentum tracking

### Sentiment Momentum (`momentum.py`)
- Sentiment change speed and acceleration (2nd derivative)
- Direction classification: accelerating, decelerating, reversing, stable
- Rapid change alert detection
- Reversal risk probability computation
- Trend analysis over configurable windows

### Divergence Detector (`divergence.py`)
- Bullish divergence: price down + sentiment up → potential bottom
- Bearish divergence: price up + sentiment down → potential top
- Monotonic trend confidence boosting
- Divergence strength and confidence scoring

### Sentiment Alpha Generator (`alpha.py`)
- News Sentiment Factor
- Social Momentum Factor
- Fear & Greed Contrarian Factor
- Composite Sentiment Factor (weighted by confidence)
- Auto-signal ID generation and history tracking

### Sentiment Memory (`memory.py`)
- Historical sentiment storage with market outcomes
- Signal accuracy tracking by emotion state
- Accuracy reports and emotion distribution analysis
- Most reliable emotion identification

### Sentiment Collector (`collector.py`)
- Multi-source data collection (news, social, forum, analyst, options, market)
- Source registration with custom collector functions
- Rich filtering by source, symbol, entity, confidence, extremity
- Score and strength aggregation

### Service Orchestration (`service.py`)
- Full pipeline: NLP → Emotion → Fear/Greed → Momentum → Divergence → Alpha → Memory
- Per-symbol sentiment summary
- Market mood assessment
- Memory reporting

## Future Upgrade

Production Features:

- LLM Financial Sentiment Model (fine-tuned BERT/GPT for finance)
- Real-Time Social Media Monitoring (Twitter/X, Reddit, StockTwits)
- Options Sentiment Analysis (unusual options flow detection)
- Investor Emotion Prediction (ML-based emotion forecasting)
- Sentiment Reinforcement Learning (RL-based sentiment trading)
- Multi-language financial NLP support
- Real-time sentiment dashboard
- Cross-asset sentiment contagion detection

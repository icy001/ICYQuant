# AI Trading Review & Learning Engine

## Responsibility

The AI Trading Review & Learning Engine closes the ICYQuant learning loop. After trades complete, it automatically analyzes outcomes, detects mistakes, extracts lessons, and feeds insights back to strategies, decision engines, and AI agents — enabling continuous improvement.

Provides:

- Trade Outcome Analysis
- Strategy Feedback Loop
- Mistake Detection
- Learning Memory (Quant Experience Database)
- Performance Attribution
- Trading Journal Generation
- Continuous Improvement Workflow

## Architecture

```
Execution (Part 20)
      ↓
Trade Completed
      ↓
Trading Learning Engine
      ├── Outcome Analyzer (outcome.py)
      ├── Strategy Feedback (feedback.py)
      ├── Mistake Detector (mistake.py)
      ├── Performance Attribution (attribution.py)
      ├── Learning Memory (memory.py)
      └── Journal Generator (journal.py)
      ↓
TradingLearningService (service.py)
      ↓
Strategy Improvement / Model Feedback
```

## Modules

### TradeResult (`trade_result.py`)

Comprehensive trade data model with entry/exit prices, PnL, timing, execution quality, strategy context, and market regime tags.

### OutcomeAnalyzer (`outcome.py`)

Scores trades on four dimensions (0-100):
- **Profitability (0-40)**: Absolute and percentage return
- **Execution Quality (0-20)**: Entry/exit slippage
- **Holding Efficiency (0-20)**: Return per day held
- **Strategy Discipline (0-20)**: Target adherence, stop-loss respect

Quality ratings: `excellent`, `good`, `fair`, `poor`.

### StrategyFeedbackEngine (`feedback.py`)

Analyzes a strategy's recent trades to compute:
- Win rate, profit factor, average win/loss
- Maximum drawdown, Sharpe estimate
- Status: `improving`, `stable`, `deteriorating`, `critical`
- Action: `increase`, `maintain`, `reduce`, `pause`, `stop`

### MistakeDetector (`mistake.py`)

Detects 8 categories of trading mistakes:
1. Late entry (high entry slippage)
2. Poor exit (high exit slippage)
3. Stop-loss violation
4. Over-positioning (high risk score + large quantity)
5. Early exit (cutting winners too soon)
6. Holding losers too long
7. Emotion bias (poor execution on both sides)
8. No stop-loss set

Severity levels: `none`, `minor`, `moderate`, `major`, `critical`.

### LearningMemory (`memory.py`)

Quant Experience Database that stores and queries learning records. Supports:
- Query by symbol, strategy, outcome, market regime, tags
- Win rate computation by symbol and market regime
- Common mistake identification
- Cumulative summary statistics

### AttributionEngine (`attribution.py`)

Decomposes trade returns into sources:
- **Alpha**: Strategy-specific edge
- **Market Beta**: Broad market contribution
- **Sector**: Sector-specific contribution
- **Timing**: Entry/exit timing quality
- **Execution**: Slippage cost
- **Residual**: Unexplained portion

### TradingJournalGenerator (`journal.py`)

Generates institutional-grade trading journals with:
- Trade thesis and rationale
- Entry/exit reasoning
- Risk management assessment
- Execution quality review
- Outcome and reflection
- Lessons and improvement plans
- Markdown export support

### TradingLearningService (`service.py`)

Unified API for the complete learning loop:
1. `review()` — Analyze trade outcome
2. `strategy_feedback()` — Generate strategy performance feedback
3. `detect_mistakes()` — Identify trading errors
4. `attribute()` — Decompose performance
5. `store_learning()` — Save to experience database
6. `generate_journal()` — Create journal entry
7. `learn()` — Run the complete learning loop

## Learning Workflow

```
Trade Completed
      ↓
Outcome Analysis
      ↓
Mistake Detection
      ↓
Performance Attribution
      ↓
Knowledge Extraction
      ↓
Store in Learning Memory
      ↓
Generate Journal
      ↓
Model Feedback → Strategy Improvement
```

## Integration Points

- **Upstream**: Execution Intelligence Engine (Part 20) produces completed trades
- **Downstream**: Autonomous Strategy Evolution (Part 22) consumes learning insights
- **Cross-cutting**: Feedback flows to Alpha Engine, Decision Engine, Risk Engine, Portfolio Manager, and Trading Copilot

## Future Upgrade

Production Features:
- Reinforcement Learning Loop
- Automated Strategy Evolution
- Behavioral Analysis (trader psychology patterns)
- AI Trading Coach (interactive feedback)
- Experience Replay System (prioritized learning from impactful trades)
- Real-time trade review dashboard

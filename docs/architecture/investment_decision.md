# AI Autonomous Investment Decision Engine


## Responsibilities

- Investment Thesis Generation
- Opportunity Evaluation
- AI Investment Committee
- Bull Case Analysis
- Bear Case Analysis
- Conviction Scoring
- Investment Decision
- Decision Explanation
- Decision Review
- Investment Memory


## Architecture

```
         AI Autonomous Investment Decision Engine


                      │


   ┌──────────────────┼──────────────────┐


   │                  │                  │


 Thesis Agent     Decision Committee   Review Agent


   │                  │                  │


 Investment       Approval Logic      Outcome Analysis


   │                  │                  │


   └──────────────────┼──────────────────┘


                      │


            Investment Memory
```


## Core Modules

### 1. Investment Thesis Generator (`thesis.py`)

Autonomously generates structured investment theses from opportunities.

- **InvestmentThesis**: Dataclass capturing thesis type, why buy, why now, catalyst, risks, exit conditions
- **ThesisType**: Enum (GROWTH, VALUE, MOMENTUM, EVENT_DRIVEN, MACRO, SECTOR_ROTATION, RELATIVE_VALUE)
- **ThesisConfidence**: Enum (LOW, MEDIUM, HIGH, VERY_HIGH)
- **ThesisEvidence**: Dataclass for structured evidence (fundamental, technical, macro, sentiment)

### 2. Opportunity Evaluation Engine (`opportunity.py`)

Multi-dimensional evaluation of investment opportunities.

- **OpportunityEvaluation**: Dataclass with scores across 4 dimensions (market opportunity, competitive advantage, growth potential, valuation)
- **OpportunityRating**: Enum (EXCELLENT, GOOD, FAIR, POOR, REJECT)
- **ValuationLevel**: Enum (UNDERVALUED, FAIR_VALUE, OVERVALUED, EXTREMELY_OVERVALUED)
- Weighted scoring: Market Opportunity 25%, Competitive Advantage 20%, Growth 25%, Valuation 30%

### 3. AI Investment Committee (`committee.py`)

Simulates an institutional investment committee with debate and voting.

- **Committee Members**: Bull Analyst, Bear Analyst, Risk Analyst, Portfolio Manager
- **VoteType**: Enum (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL, ABSTAIN)
- **CommitteeDecision**: Dataclass capturing all votes, consensus, debate summary
- Consensus determined by weighted vote aggregation with dispersion penalty

### 4. Bull Case Agent (`bull_agent.py`)

Analyzes the bullish case for an investment.

- Identifies growth drivers, catalysts, competitive advantages
- Calculates bullish conviction score (0-1)
- Generates narrative and required conditions
- **BullCaseAnalysis**: Dataclass with full bull case details

### 5. Bear Case Agent (`bear_agent.py`)

Analyzes the bearish case and risks.

- Identifies risk factors, bubble indicators, failure scenarios
- Calculates risk intensity score (0-1)
- Estimates max drawdown
- Generates invalidation points
- **BearCaseAnalysis**: Dataclass with full bear case details

### 6. Conviction Score Engine (`conviction.py`)

Multi-dimensional conviction scoring.

- **Input**: Bull case, bear case, committee votes
- **Factors**: Bull contribution (35%), Bear penalty (25%), Risk adjustment (20%), Committee alignment (20%)
- **ConvictionLevel**: VERY_STRONG (85+), STRONG (70+), MODERATE (50+), WEAK (30+), NO_CONVICTION (<30)
- Outputs human-readable label (e.g., "STRONG BUY - Very High Conviction")

### 7. Investment Decision Engine (`decision.py`)

Final investment decision based on conviction score.

- **DecisionType**: BUY, STRONG_BUY, HOLD, REDUCE, SELL, REJECT
- **DecisionUrgency**: IMMEDIATE, SHORT_TERM, MEDIUM_TERM, OPPORTUNISTIC
- Generates position sizing, stop loss, take profit
- Generates risk controls specific to each decision type
- **InvestmentDecision**: Complete dataclass with all execution parameters

### 8. Decision Explanation Engine (`explanation.py`)

Transparent explanation of investment decisions.

- Explains why this decision was made
- Lists evidence used
- Identifies risk considerations
- Specifies what would invalidate the decision
- Lists alternatives considered
- Calculates transparency score

### 9. Decision Review Engine (`review.py`)

Post-mortem analysis comparing predictions to reality.

- **ReviewOutcome**: CORRECT, PARTIALLY_CORRECT, INCORRECT, INCONCLUSIVE
- **ErrorSource**: Identifies root cause (THESIS_ERROR, MODEL_ERROR, TIMING_ERROR, RISK_ASSESSMENT_ERROR, etc.)
- Generates lessons learned and improvement actions
- Calculates review quality score

### 10. Investment Decision Memory (`memory.py`)

Institutional investment memory system.

- **InvestmentMemoryEntry**: Complete record of decision and outcome
- **DecisionPattern**: Pattern recognition with win rates
- **DecisionCategory**: WIN, LOSS, BREAKEVEN, MISSED_OPPORTUNITY
- Institutional knowledge base per symbol
- Pattern extraction for continuous learning


## Autonomous Investment Decision Loop

```
Market Data → Research → Thesis Generation → Committee Debate
→ Conviction Score → Investment Decision → Portfolio Action
→ Outcome Review → Learning
```


## Service Orchestrator

`InvestmentDecisionService` orchestrates the full loop:

1. Investment Thesis Generation
2. Opportunity Evaluation
3. Bull Case Analysis
4. Bear Case Analysis
5. Committee Discussion
6. Conviction Scoring
7. Investment Decision
8. Decision Explanation
9. Decision Review (post-outcome)
10. Memory Recording


## Future Upgrade

- Autonomous Investment Committee Debate
- Reinforcement Learning Decision System
- Multi Asset Decision Engine
- AI Portfolio Manager Integration
- Self Improving Investment Process

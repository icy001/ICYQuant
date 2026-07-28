# AI Decision Intelligence Center

## Responsibilities

- Multi-Agent Decision Fusion
- Decision Conflict Detection
- Confidence Aggregation
- Decision Arbitration
- Compliance Validation
- Final Decision Generation

## Architecture

```
All Intelligence Engines
        │
        ▼
Decision Collector
        │
Decision Fusion Engine
        │
Conflict Detector
        │
Confidence Aggregator
        │
Risk Validator
        │
Compliance Validator
        │
Decision Arbitration Engine
        │
Explainable AI
        │
Execution Engine
```

## Workflow

```
All Intelligence
    ↓
Decision Collection
    ↓
Fusion
    ↓
Conflict Analysis
    ↓
Risk Validation
    ↓
Compliance Validation
    ↓
Decision Arbitration
    ↓
Final Decision
    ↓
Execution
```

## Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| collector | `DecisionCollector` / `DecisionPackage` | Unified ingestion of decisions from all engines |
| fusion | `MultiAgentFusionEngine` | Confidence-weighted, Bayesian, and voting fusion |
| conflict | `ConflictDetectionEngine` / `ConflictReport` | Signal disagreement detection and scoring |
| confidence | `ConfidenceAggregator` | Overall confidence from all agents |
| arbitration | `DecisionArbitrationEngine` | Priority-based conflict resolution |
| compliance | `ComplianceValidator` / `ComplianceResult` | Risk, exposure, blacklist, trading rule checks |
| final_decision | `FinalDecisionGenerator` / `FinalDecision` | Single source of truth decision |
| timeline | `DecisionTimeline` | Full decision audit trail |
| memory | `DecisionMemory` | Decision knowledge base with outcome tracking |
| service | `DecisionCenterService` | Orchestrates the complete pipeline |

## Priority Order (Default)

```
risk > macro > strategy > portfolio > sentiment > execution > simulation
```

## Future Upgrade

- Hierarchical Multi-Agent System
- LLM Decision Coordinator
- Reinforcement Learning Arbitration
- Distributed Decision Cluster
- Human-in-the-Loop Review

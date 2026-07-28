# AI Explainable Intelligence Engine

## Responsibilities

- Decision Attribution
- Feature Importance Analysis
- Decision Path Construction
- Confidence Evaluation
- Rule Validation
- Model Audit
- Human-readable Explanation

## Architecture

```
AI Models
    ↓
Decision Collector
    ↓
Reasoning Graph
    ↓
Explanation Engine
    ├── Signal Attribution
    ├── Feature Importance
    ├── Decision Path
    ├── Confidence Analysis
    ├── Model Audit
    ├── Rule Validation
    └── Human Explanation
    ↓
Explainable Report
```

## Workflow

```
AI Decision
    ↓
Reason Collection
    ↓
Feature Attribution
    ↓
Decision Path
    ↓
Confidence Analysis
    ↓
Human Explanation
    ↓
Audit
    ↓
Knowledge Base
```

## Modules

| Module | Class | Responsibility |
|--------|-------|----------------|
| collector | `DecisionCollector` / `DecisionEvent` | Collects and normalizes decisions from all upstream engines |
| attribution | `SignalAttributionEngine` | Decomposes signal into module contributions |
| importance | `FeatureImportanceAnalyzer` | Ranks features by importance score |
| decision_path | `DecisionPathEngine` | Builds causal reasoning chains |
| confidence | `ConfidenceAnalyzer` | Converts probability to confidence score & level |
| validation | `RuleValidationEngine` | Validates against risk, position, compliance rules |
| audit | `ModelAuditEngine` | Records model/parameter/prompt versions |
| explanation | `HumanExplanationGenerator` | Produces trader-readable explanations |
| memory | `ExplainableMemory` | Persistent knowledge base for explanations |
| service | `ExplainableAIService` | Orchestrates the full XAI pipeline |

## Future Upgrade

- SHAP Integration
- LIME Integration
- Counterfactual Explanation
- Causal Inference Analysis
- Interactive Decision Graph
- Regulatory Compliance Report

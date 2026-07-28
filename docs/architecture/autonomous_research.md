# Autonomous Research Workflow Engine

## Responsibility

Provides:
- Research Planning
- Task Decomposition
- Workflow Execution
- Experiment Automation

## Architecture

```
Goal → Planner → Workflow → Agents → Evaluation
```

## Modules

| Module | File | Purpose |
|--------|------|---------|
| ResearchGoal | `goal.py` | Research goal model with lifecycle |
| ResearchTask | `task.py` | Task model with dependencies and status |
| ResearchWorkflow | `workflow.py` | DAG-based workflow with task graph |
| ResearchPlanner | `planner.py` | Converts goals into task pipelines |
| TaskScheduler | `scheduler.py` | Executes tasks respecting dependencies |
| ExperimentLoop | `experiment.py` | Automated experiment iteration |
| ResearchEvaluator | `evaluator.py` | Evaluates results and decides go/no-go |
| AutonomousResearchService | `service.py` | Orchestrates the full pipeline |

## Pipeline

```
Research Goal
    ↓
Planning (ResearchPlanner)
    ↓
Task Generation (ResearchTask)
    ↓
Agent Execution (TaskScheduler)
    ↓
Experiment (ExperimentLoop)
    ↓
Evaluation (ResearchEvaluator)
    ↓
Knowledge Update
    ↓
New Research
```

## Evaluation Criteria

| Metric | Threshold | Decision |
|--------|-----------|----------|
| Sharpe < 0.3 | Discard | Strategy rejected |
| Sharpe 0.3-0.8 | Continue | Optimize further |
| Sharpe > 0.8 | Accept | Strategy approved |
| IC < 0.01 | Discard | Regardless of Sharpe |

## Future Upgrade

Production Features:
- LLM Planning Agent
- Workflow DAG Engine
- Auto Experiment Generation
- Reinforcement Learning Research
- Autonomous Strategy Discovery

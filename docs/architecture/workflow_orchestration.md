# Workflow Orchestration Service


## Responsibility


Provides:


- Business workflow execution

- Multi service coordination

- Saga transaction support

- Compensation handling


## Example


Order Workflow:


```
Order
|
Risk
|
Execution
|
Ledger
```


## Future Upgrade


Production Features:


- Temporal Integration

- Workflow Persistence

- Distributed Scheduler

- State Recovery

- Human Approval Step

- Long Running Workflow

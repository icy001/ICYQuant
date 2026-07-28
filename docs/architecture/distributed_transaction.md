# Distributed Transaction Coordinator

## Responsibility

Provides:

- Saga Transaction
- TCC Transaction
- Two Phase Commit
- Compensation
- Recovery

## Architecture

```text
Trading Request

↓

Coordinator

↓

Saga / TCC / 2PC

↓

Recovery
```

## Future Upgrade

Production Features:

- Outbox Pattern
- Inbox Pattern
- Transaction Timeout
- Dead Letter Queue
- Transaction Metrics
- OpenTelemetry Trace Integration
- Transaction Dashboard
- Automatic Retry Policy

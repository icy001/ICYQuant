# Event Sourcing Storage Engine

## Responsibility

Provides:

- Immutable Event Store
- Event Stream
- Snapshot
- Replay
- Projection

## Architecture

```text
Command

↓

Event Store

↓

Replay

↓

State
```

## Future Upgrade

Production Features:

- Kafka Event Log
- Event Schema Registry
- Event Version Migration
- CQRS Architecture
- Transactional Outbox
- Event Replay Dashboard
- Compliance Audit Export

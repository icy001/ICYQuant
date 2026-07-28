# Event Replay & Recovery Service

## Responsibility

Provides:

- Event replay
- State reconstruction
- Failure recovery
- Disaster recovery support

## Flow

Event Store

|
v
Event Reader

|
v
Replay Engine

|
v
Recovered State

## Future Upgrade

Production Features:

- Kafka Event Replay
- Event Sourcing Database
- Snapshot Recovery
- Checkpoint Mechanism
- Automatic Recovery Workflow
- Cross Region Disaster Recovery
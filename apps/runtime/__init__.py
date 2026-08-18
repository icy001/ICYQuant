"""ICYQuant Runtime.

Deployment & Validation runtime: wires the official engine chain
(Signal -> Risk -> Order -> Execution -> Position -> Ledger -> Reconciliation)
using the in-memory EventBus, and exposes per-service health checks.

Feature Freeze: this layer wires existing engines, it does NOT add new engines.
"""

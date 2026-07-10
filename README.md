# ICYQuant

> Institutional-grade quantitative trading infrastructure.

## Core Positioning

ICYQuant is a production-grade quantitative trading infrastructure designed for institutional-grade trading operations.

## Current Module

### Ledger Service (v0.3.0-beta2)

ICYQuant Ledger uses an event sourced architecture.

The ledger stores facts, not state.

Example:

```
ExecutionReport
    ↓
LedgerEvent
    ↓
EventStore
    ↓
Projection
    ↓
Portfolio State
```

Supported stores:

- MemoryEventStore
- SQLiteEventStore

Future:

- PostgreSQL Event Store
- Kafka Event Stream

### Reconciliation Engine (v0.2.4)

**Purpose:** Detect, Analyze, Replay, Repair, Verify, Audit state inconsistency between trading components.

## Features

### Production Reconciliation Engine (v0.2.4)

- **Domain Models**: PositionSnapshot, LedgerSnapshot, ReconciliationResult
- **Compare Engine**: Ledger vs Position difference detection
- **Event Store**: Event sourcing abstraction with persistence layer
- **Trade Event**: Domain event with apply method for position calculation
- **Snapshot Engine**: Avoid replaying millions of events
- **Replay Engine V2**: Rebuild position from snapshot + incremental events
- **Repair Engine**: RepairCommand pattern + RepairWorkflow with audit trail
- **Audit Trail**: Track action, symbol, before/after, reason, timestamp
- **API Layer**: REST API v1 with health check, reconciliation, repair endpoints
- **Monitoring**: Prometheus metrics + Grafana dashboard
- **Persistence**: PostgreSQL + Redis + Kafka integration
- **Testing**: Complete unit test framework

## Technology Stack

- Python 3.9+
- FastAPI
- PostgreSQL 16
- Redis 7
- Kafka (Confluent)
- Docker / Docker Compose
- Pytest
- Ruff
- Prometheus
- Grafana

## Repository Structure

```
ICYQuant/
├── common/              # Base classes and exceptions
├── contracts/           # Shared event/command contracts
│   └── events/          # Event definitions (BaseEvent, TradeEvent)
├── infrastructure/      # Infrastructure layer
│   ├── database/        # PostgreSQL + migrations
│   ├── cache/           # Redis cache
│   └── messaging/       # Kafka adapter
├── services/
│   ├── eventstore/      # Event sourcing abstraction
│   ├── ledger/          # Ledger service
│   ├── position/        # Position service
│   ├── execution/       # Execution service
│   ├── eventbus/        # Event bus
│   └── reconciliation/  # Reconciliation Engine
│       ├── api/         # REST API v1 endpoints
│       ├── domain/      # Domain layer (ReconciliationEngine)
│       ├── application/ # Application service
│       ├── repository/  # Repository layer
│       ├── compare/     # Comparator framework
│       ├── repair/      # Repair workflow
│       ├── replay/      # Event replay engine
│       ├── scheduler/   # Scheduling
│       ├── snapshot/    # Snapshot management
│       └── metrics/     # Prometheus metrics
├── monitoring/          # Monitoring stack
│   ├── prometheus/      # Prometheus configuration
│   └── grafana/         # Grafana dashboards
├── tests/               # Unit tests
├── docs/                # Documentation
├── docker-compose.yml   # Docker environment
├── Makefile             # Development commands
└── pyproject.toml       # Project configuration
```

## Development Status

**Current Version:** v0.2.4 (Production Release)

### v0.2.4 Production Status

| Feature | Status |
|---------|--------|
| Production Reconciliation Engine | ✅ |
| Event Sourcing | ✅ |
| Snapshot Recovery | ✅ |
| Automated Repair | ✅ |
| Audit Trail | ✅ |
| Persistence Layer | ✅ |
| Monitoring Stack | ✅ |
| Deployment Workflow | ✅ |
| API v1 | ✅ |

## Getting Started

### Prerequisites

- Python 3.9+
- Docker
- Docker Compose

### Installation

```bash
make install
```

### Run Tests

```bash
make test
```

### Start All Services

```bash
docker compose up -d
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/reconciliation/run` | POST | Run reconciliation |
| `/api/v1/reconciliation/repair` | POST | Execute repair |

## Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Reconciliation API**: http://localhost:8000

## Metrics

| Metric | Description |
|--------|-------------|
| `icyquant_reconciliation_total` | Total reconciliation runs |
| `icyquant_mismatch_total` | Total mismatches detected |
| `icyquant_repair_success_total` | Total successful repairs |
| `icyquant_repair_failed_total` | Total failed repairs |
| `icyquant_replay_latency` | Replay latency in seconds |

## Roadmap

- **Sprint 2.4**: Reconciliation Engine (Completed)
- **Sprint 2.5**: Position Context & Comparator Implementations
- **Sprint 3.0**: Broker Adapters (IBKR, MT5, CTP, FIX)

## License

MIT License. See LICENSE file.

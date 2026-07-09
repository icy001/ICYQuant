# ICYQuant

> Institutional-grade quantitative trading infrastructure.

## Core Positioning

ICYQuant is a production-grade quantitative trading infrastructure designed for institutional-grade trading operations.

## Current Module

### Reconciliation Engine

**Purpose:** Detect, Analyze, Repair state inconsistency between trading components.

## Features

### Reconciliation Engine (v0.2.4-alpha2)

- **Domain Models**: PositionSnapshot, LedgerSnapshot, ReconciliationResult
- **Compare Engine**: Ledger vs Position difference detection
- **Event Store**: Event sourcing abstraction with in-memory storage
- **Trade Event**: Domain event with apply method for position calculation
- **Snapshot Engine**: Avoid replaying millions of events
- **Replay Engine V2**: Rebuild position from snapshot + incremental events
- **Repair Engine**: RepairCommand pattern + RepairWorkflow with audit trail
- **Audit Trail**: Track who, when, why, and what changed
- **API Layer**: FastAPI with health check endpoint
- **Testing**: Complete unit test framework

## Technology Stack

- Python 3.9+
- FastAPI
- PostgreSQL 16
- Redis 7
- Docker / Docker Compose
- Pytest
- Ruff

## Repository Structure

```
ICYQuant/
├── common/              # Base classes and exceptions
├── contracts/           # Shared event/command contracts
│   └── events/          # Event definitions (BaseEvent, TradeEvent)
├── services/
│   ├── eventstore/      # Event sourcing abstraction
│   └── reconciliation/  # Reconciliation Engine
│       ├── api/         # REST API endpoints
│       ├── compare/     # Comparator framework
│       ├── models/      # Domain models
│       ├── repair/      # Repair workflow
│       ├── replay/      # Event replay engine
│       ├── scheduler/   # Scheduling
│       └── snapshot/    # Snapshot management
├── tests/               # Unit tests
├── docs/                # Documentation
├── docker-compose.yml   # Docker environment
├── Makefile             # Development commands
└── pyproject.toml       # Project configuration
```

## Development Status

**Current Version:** v0.2.4-alpha2

### Alpha2 Completion Status

| Ability | Status |
|---------|--------|
| Mismatch Detection | ✅ |
| Event Store | ✅ |
| Trade Event Model | ✅ |
| Snapshot | ✅ |
| Replay Rebuild | ✅ |
| Repair Workflow | ✅ |
| Audit Trail | ✅ |
| Persistence Interface | ✅ |
| Test Suite | ✅ |

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

### Start Docker Environment

```bash
docker-compose up -d
```

## Roadmap

- **Sprint 2.4**: Reconciliation Engine (Current)
- **Sprint 2.5**: Position Context & Comparator Implementations
- **Sprint 3.0**: Production Readiness

## License

MIT License. See LICENSE file.

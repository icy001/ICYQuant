# ICYQuant

> Institutional-grade quantitative trading infrastructure.

## Core Positioning

ICYQuant is a production-grade quantitative trading infrastructure designed for institutional-grade trading operations.

## Current Module

### Reconciliation Engine

**Purpose:** Detect, Analyze, Repair state inconsistency between trading components.

## Features

### Reconciliation Engine (v0.2.4-alpha1)

- **Domain Models**: PositionSnapshot, LedgerSnapshot, ReconciliationResult
- **Compare Engine**: Ledger vs Position difference detection
- **Replay Engine**: Event-based position rebuilding
- **Repair Engine**: RepairCommand pattern for automated fixes
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
├── services/
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

**Current Version:** v0.2.4-alpha1

### Alpha1 Completion Status

| Module | Status |
|--------|--------|
| Repository Structure | ✅ |
| Reconciliation Domain | ✅ |
| Compare Engine | ✅ |
| Replay Engine | ✅ |
| Repair Engine | ✅ |
| API Health Check | ✅ |
| Tests | ✅ |
| Docker Environment | ✅ |

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

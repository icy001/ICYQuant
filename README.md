# ICYQuant

> Institutional-grade quantitative trading infrastructure.

## 文档导航

| 文档 | 说明 |
|------|------|
| [使用文档](docs/USAGE_GUIDE.md) | **已部署环境的使用指南**：API、验证 CLI、日常运维、排查 |
| [验证报告](docs/VALIDATION_REPORT.md) | 各阶段验证结果汇总（Gate / Paper / Shadow / Strategy） |
| [入门指南](docs/getting_started.md) | 从零开始部署与使用 |
| [操作手册](docs/operator_guide.md) | 生产运维、监控、备份与故障恢复 |
| [Docker 部署](docs/03-operations/DOCKER_DEPLOYMENT.md) | Docker / Compose 部署细节 |

## Core Positioning

ICYQuant is a production-grade quantitative trading infrastructure designed for institutional-grade trading operations.

## Current Module

### Core & Shared Foundation (v0.4.0-alpha2)

ICYQuant is built on a modular core/shared foundation that provides:

- **Core Domain**: Base classes, entities, and value objects
- **Shared Contracts**: Event/command definitions shared across all services
- **Infrastructure Abstractions**: Pluggable database, cache, and messaging adapters

### Ledger Service (v0.4.0-alpha2)

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
- PostgreSQL Event Store
- Kafka Event Stream

### Reconciliation Engine (v0.4.0-alpha2)

**Purpose:** Detect, Analyze, Replay, Repair, Verify, Audit state inconsistency between trading components.

## Features

### Production Reconciliation Engine (v0.4.0-alpha2)

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

- Python 3.12+
- FastAPI
- PostgreSQL 16
- Redis 7
- Kafka 3.8 (Bitnami)
- Docker / Docker Compose
- Pytest
- Ruff
- Prometheus
- Grafana
- OpenTelemetry

## Repository Structure

```
ICYQuant/
├── apps/               # Application modules
│   ├── api/            # FastAPI REST API
│   ├── worker/         # Background worker
│   ├── ledger/         # Ledger service
│   ├── reconciliation/ # Reconciliation engine
│   └── execution/      # Execution service
├── core/               # Core domain foundation
│   ├── domain/         # Base classes, entities, value objects
│   ├── contracts/      # Shared event/command contracts
│   └── exceptions/     # Domain exceptions
├── shared/             # Shared utilities and abstractions
│   ├── infrastructure/ # Database, cache, messaging adapters
│   └── config/         # Configuration management
├── services/           # Business logic services
│   ├── eventstore/     # Event sourcing abstraction
│   ├── ledger/         # Ledger service
│   ├── position/       # Position service
│   ├── execution/      # Execution service
│   └── reconciliation/  # Reconciliation Engine
├── monitoring/          # Monitoring stack
│   ├── prometheus/     # Prometheus configuration
│   └── grafana/        # Grafana dashboards
├── tests/               # Unit tests
├── docs/                # Documentation
├── docker-compose.yml   # Docker environment
├── Makefile             # Development commands
└── pyproject.toml       # Project configuration
```

## Development Status

**Current Version:** v0.4.0-alpha2 (Alpha Release)

### v0.4.0-alpha2 Status

| Feature | Status |
|---------|--------|
| Core & Shared Foundation | ✅ |
| Modular Application Architecture | ✅ |
| Production Reconciliation Engine | ✅ |
| Event Sourcing | ✅ |
| Snapshot Recovery | ✅ |
| Automated Repair | ✅ |
| Audit Trail | ✅ |
| Persistence Layer | ✅ |
| Monitoring Stack | ✅ |
| Deployment Workflow | ✅ |
| API v1 | ✅ |
| Kafka Integration | ✅ |
| OpenTelemetry Tracing | ✅ |

## Getting Started

### Prerequisites

- Python 3.12+
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
- **Sprint 4.0**: Core/Shared Foundation & Modular Architecture (In Progress)

## License

MIT License. See LICENSE file.

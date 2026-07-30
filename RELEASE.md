# ICYQuant v0.4.0-alpha1 GA Release

---

## Release Overview

ICYQuant v0.4.0-alpha1 GA is the **first General Availability release** of the Institutional Quant Operating System, representing a complete, production-grade platform for quantitative trading operations. This release includes 11 core modules spanning the full trading lifecycle — from research and AI-driven alpha generation to execution, risk management, portfolio oversight, and production observability.

The GA (General Availability) designation signifies that this release has passed all quality gates, security audits, and performance benchmarks, and is approved for production deployment.

---

## Version Information

| Attribute | Value |
|-----------|-------|
| **Version** | v0.4.0-alpha1 |
| **Stage** | GA (General Availability) |
| **Release Date** | 2026-07-30 |
| **License** | MIT |
| **API Version** | v1 |
| **Docker Tag** | `icyquant:v0.4.0-alpha1` |
| **Helm Chart Version** | 0.4.0-alpha1 |
| **Python SDK Version** | 0.4.0a1 |

---

## Key Features

### 1. Research Module
- Alpha factor research and signal generation
- Factor IC/IR analysis and ranking
- Multi-asset universe management
- Data validation and preprocessing pipelines
- Event-driven research execution framework

### 2. AI Module
- AI/ML model training, inference, and deployment pipeline
- LLM provider integration for decision support
- AI Chief Investment Officer (AI-CIO) engine
- Agent-based trading decision workflows
- Retrieval-Augmented Generation (RAG) for research context
- AutoML service for automated model selection

### 3. Backtest Module
- Historical simulation with realistic market conditions
- Multi-threaded backtest engine with event-driven architecture
- Risk-adjusted performance metrics
- Transaction cost modeling and slippage simulation
- Equity curve generation and trade logging

### 4. OMS (Order Management System)
- Full order lifecycle management (Created → Validated → Risk Checked → Sent → Filled/Cancelled)
- Multi-venue order routing
- Order state machine with 7+ states
- Integration with risk checks and execution engine
- Stateless computation with stateful persistence

### 5. EMS (Execution Management System)
- Smart order types and execution algorithms
- Real-time market data integration
- Trade execution and fill processing
- Order slicing and timing strategies
- Cost-aware execution optimization

### 6. Risk Module
- Real-time risk calculation and limits enforcement
- Pre-trade risk checking (position limits, cash availability, order size)
- Value at Risk (VaR) and drawdown monitoring
- Exposure and leverage management
- Scenario analysis and stress testing
- Liquidity risk assessment

### 7. Portfolio Module
- Multi-asset portfolio tracking and PnL computation
- Portfolio drift monitoring and rebalancing
- NAV (Net Asset Value) calculation and accounting
- Cash flow management and fee engine
- KPI dashboard and analytics

### 8. Lakehouse Module
- Data lake architecture with time-travel queries
- Structured and unstructured data storage
- Data lineage tracking
- Schema evolution and data governance
- High-throughput data access layer

### 9. Observability Module
- Structured JSON logging with request context
- Distributed tracing (OpenTelemetry)
- Application metrics with Prometheus exporter
- Health check endpoints
- Audit event pipeline with immutable records
- Correlation context for full trading lifecycle

### 10. Security Module
- JWT-based authentication and session management
- RBAC (Role-Based Access Control)
- Secret management with KMS integration
- API access control and rate limiting
- Security audit logging

### 11. Platform Module
- Centralized module registry and dependency graph
- Workflow engine with multi-step execution and approval gates
- Event router with pub/sub, filtering, and priorities
- Plugin SDK for brokers, strategies, and AI models
- Runtime manager with hot-reload capability
- Scheduler for periodic and event-driven jobs
- CQRS (Command Query Responsibility Segregation) architecture

---

## Quick Start

### Docker

Deploy ICYQuant as a single container:

```bash
docker pull icyquant:v0.4.0-alpha1
docker run -d \
  -p 8000:8000 \
  -e ICYQUANT_ENV=production \
  -v ./data:/app/data \
  icyquant:v0.4.0-alpha1
```

### Helm

Deploy to a Kubernetes cluster:

```bash
helm install icyquant ./deployment/helm/ \
  --set image.tag=v0.4.0-alpha1 \
  --namespace icyquant-system \
  --create-namespace
```

### Python SDK

Install the ICYQuant SDK for Python applications:

```bash
pip install icyquant==0.4.0a1
```

```python
from icyquant import ICYQuantClient

client = ICYQuantClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# Submit a research task
result = client.research.run_alpha_factor(
    symbol="AAPL",
    factor="momentum",
    start_date="2020-01-01",
    end_date="2026-07-30"
)
```

---

## System Requirements

| Component | Minimum Version | Recommended Version |
|-----------|----------------|---------------------|
| **Python** | 3.12 | 3.12.x |
| **PostgreSQL** | 16 | 16.x |
| **Redis** | 7 | 7.x |
| **Kafka** | 3.8 | 3.8.x |
| **Kubernetes** | 1.31 | 1.31.x |
| **Docker** | 28 | 28.x |

### Hardware Requirements

| Deployment Type | CPU | Memory | Storage |
|----------------|-----|--------|---------|
| **Single Node** | 4 cores | 8 GB | 50 GB SSD |
| **Production** | 8+ cores | 16+ GB | 200+ GB SSD |
| **High Availability** | 16+ cores | 32+ GB | 500+ GB SSD |

---

## API Endpoints

### Core API v1 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | System health check |
| `/api/v1/metrics` | GET | Prometheus metrics |
| `/api/v1/auth/login` | POST | Authenticate and obtain JWT |
| `/api/v1/auth/refresh` | POST | Refresh JWT token |
| `/api/v1/research/alpha` | POST | Run alpha factor research |
| `/api/v1/research/signals` | GET | List research signals |
| `/api/v1/ai/sessions` | POST | Create AI session |
| `/api/v1/ai/chat` | POST | AI chat completion |
| `/api/v1/backtest/run` | POST | Execute backtest job |
| `/api/v1/backtest/results/{id}` | GET | Get backtest results |
| `/api/v1/oms/orders` | POST | Submit new order |
| `/api/v1/oms/orders/{id}` | GET | Get order status |
| `/api/v1/oms/orders/{id}/cancel` | POST | Cancel order |
| `/api/v1/oms/orders/{id}/fill` | POST | Submit fill |
| `/api/v1/ems/execute` | POST | Execute order |
| `/api/v1/risk/check` | POST | Perform pre-trade risk check |
| `/api/v1/risk/limits` | GET | Get current risk limits |
| `/api/v1/risk/portfolio` | GET | Get portfolio risk metrics |
| `/api/v1/portfolio/positions` | GET | List all positions |
| `/api/v1/portfolio/pnl` | GET | Get portfolio PnL |
| `/api/v1/portfolio/nav` | GET | Get NAV history |
| `/api/v1/lakehouse/query` | POST | Execute data lake query |
| `/api/v1/observability/traces` | GET | Query distributed traces |
| `/api/v1/observability/logs` | GET | Query structured logs |
| `/api/v1/security/audit` | GET | Query security audit events |
| `/api/v1/jobs` | GET | List scheduled jobs |
| `/api/v1/jobs/{id}` | POST | Trigger job execution |

### API Base URL

```
http://localhost:8000/api/v1
```

### Authentication

All API endpoints (except `/health` and `/auth/login`) require a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

---

## Migration Guide

For detailed migration instructions from previous versions, refer to the [Migration Guide](docs/migration/).

### Upgrade Path

| From Version | To Version | Notes |
|-------------|-----------|-------|
| v0.3.0-beta2 | v0.4.0-alpha1 GA | Full platform migration required |
| v0.4.0-alpha1 (alpha) | v0.4.0-alpha1 GA | Drop-in replacement, no API changes |
| v0.4.0-alpha1 RC1 | v0.4.0-alpha1 GA | Drop-in replacement, stability improvements |

### Database Migration

```bash
alembic upgrade head
```

### Configuration Update

```bash
# Copy and update configuration files
cp configs/deployment/dr.yaml configs/deployment/dr.local.yaml
# Update environment-specific settings
```

### Rollback Procedure

If the migration encounters critical issues, follow these steps to rollback:

1. **Stop all services**: `kubectl delete deployment -n icyquant-system`
2. **Restore database from backup**: Run `alembic downgrade` to revert schema changes, then restore from the most recent backup
3. **Reinstall previous Helm chart**: `helm install icyquant ./deployment/helm/ --set image.tag=previous-version --namespace icyquant-system`
4. **Verify rollback**: Run health check and smoke tests to confirm system integrity

Estimated rollback time: 15-30 minutes depending on database size.

---

## Support & Contact

### Official Channels

| Channel | Link | Description |
|---------|------|-------------|
| **Documentation** | https://docs.icyquant.io | Official API and user documentation |
| **GitHub** | https://github.com/icyquant | Source code and issue tracking |
| **Discord** | https://discord.gg/icyquant | Community discussions |
| **Email** | support@icyquant.io | Direct support for enterprise customers |

### Professional Support

For enterprise deployments, the ICYQuant team provides:
- Production deployment assistance
- Performance tuning and optimization
- Custom integration support
- 24/7 incident response
- Security consulting

Contact **enterprise@icyquant.io** for more information.

---

## Changelog

For a complete list of changes in this release and previous versions, see the [CHANGELOG.md](CHANGELOG.md) file.

---

## License

ICYQuant is released under the **MIT License**. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.

---

*ICYQuant v0.4.0-alpha1 GA — First General Availability release. Production-ready institutional quant operating system.*
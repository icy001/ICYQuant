# Changelog


## v0.4.0-alpha1 (GA)

**Release Date**: 2026-07-30

This is the **first General Availability release** of ICYQuant, representing a complete institutional-grade quantitative trading platform with 11 core modules.

---

### Added

- **Research Module**
  - Alpha factor research and signal generation framework
  - Factor IC/IR analysis and multi-asset ranking
  - Universe management and data validation pipelines
  - Event-driven research execution engine

- **AI Module**
  - AI/ML model training, inference, and deployment pipeline
  - AI Chief Investment Officer (AI-CIO) engine for strategic asset allocation
  - LLM provider integration with tool-use capabilities
  - Agent-based trading decision workflows with memory and policy
  - Retrieval-Augmented Generation (RAG) for research context
  - AutoML service for automated model selection and hyperparameter tuning

- **Backtest Module**
  - Event-driven backtest engine with realistic market simulation
  - Transaction cost modeling and slippage simulation
  - Equity curve generation and risk-adjusted performance metrics
  - Multi-threaded execution for high-speed historical replay

- **OMS (Order Management System)**
  - Full order lifecycle management with 7+ state machine
  - Multi-venue order routing and smart order types
  - Pre-trade risk check integration
  - Order persistence with audit trail
  - RESTful API for order submission, cancellation, and fill management

- **EMS (Execution Management System)**
  - Smart order execution algorithms
  - Real-time market data integration for execution decisions
  - Order slicing and timing strategies
  - Cost-aware execution optimization

- **Risk Module**
  - Real-time risk calculation and limits enforcement (position, leverage, exposure)
  - Value at Risk (VaR) and drawdown monitoring
  - Scenario analysis and stress testing engine
  - Liquidity risk assessment and margin monitoring
  - Risk rule registry with pluggable rule types

- **Portfolio Module**
  - Multi-asset portfolio tracking and PnL computation
  - Portfolio drift monitoring and automated rebalancing
  - NAV calculation, accounting, and fee engine
  - Cash flow management and analytics dashboard
  - Portfolio audit trail and KPI tracking

- **Lakehouse Module**
  - Data lake architecture with time-travel query support
  - Structured and unstructured data storage
  - Data lineage tracking for compliance
  - Schema evolution and data governance layer

- **Observability Module**
  - Structured JSON logging with request_id/trace_id correlation
  - Distributed tracing via OpenTelemetry
  - Prometheus metrics exporter with application metrics
  - Health check endpoint and error tracking
  - Audit event pipeline with immutable records

- **Security Module**
  - JWT-based authentication and session management
  - Role-Based Access Control (RBAC) for API authorization
  - Secret management with KMS integration and rotation
  - API access control and rate limiting
  - Security audit logging and monitoring

- **Platform Module**
  - Centralized module registry with dependency graph resolution
  - Workflow engine with multi-step execution and approval gates
  - Event router with pub/sub, filtering, and priorities
  - Plugin SDK for brokers, strategies, and AI model extensions
  - Runtime manager with module hot-reload capability
  - CQRS architecture with command/query separation
  - Scheduler for periodic and event-driven job execution

- **Infrastructure & Deployment**
  - Docker containerization with production-ready Dockerfile
  - Helm chart for Kubernetes deployment
  - Docker Compose for local development
  - Alembic database migration framework
  - PostgreSQL, Redis, Kafka integration
  - Python SDK (`icyquant==0.4.0a1`)
  - OpenAPI v1 specification

### Changed

- Upgraded Python requirement to 3.12+
- Upgraded PostgreSQL requirement to 16+
- Upgraded Redis requirement to 7+
- Upgraded Kafka requirement to 3.8+
- API version changed to v1 with stable endpoints
- CQRS architecture adopted across all services
- Event-driven design standardized as core architectural pattern
- Unified structured logging format across all modules

### Fixed

- Resolved event store consistency issues under high concurrency
- Fixed ledger replay accuracy for large datasets
- Corrected risk calculation edge cases in portfolio VaR
- Improved backtest result reproducibility with deterministic random seed
- Enhanced API gateway error handling and validation
- Stabilized distributed tracing under high TPS workloads

### Security

- Implemented JWT-based authentication with configurable expiration
- Added RBAC authorization model with role and permission management
- Integrated secret management with KMS and automated rotation
- Enabled API rate limiting to prevent abuse
- Added security audit logging for all sensitive operations
- Performed third-party security audit with zero critical vulnerabilities
- SBOM (Software Bill of Materials) generated and published

---

## v0.3.0-beta2


### Added


- Institutional Observability Layer
  - Structured logging with JSON format
  - Request context with request_id/trace_id
  - Distributed tracing (OpenTelemetry foundation)
  - Error tracking and exception handling
  - Application metrics collection
  - Prometheus exporter endpoint
  - Health check endpoint (/health)
  - Configuration settings with environment variables
  - Correlation context for trading lifecycle
  - Audit event pipeline with immutable records
- Event sourced ledger core
- LedgerEvent domain model
- Memory event store
- SQLite persistent event store
- Ledger repository abstraction
- Ledger replay source
- Portfolio projections (Position/Cash)
- Projection engine
- Replay engine
- Portfolio snapshot persistence
- Audit service with PostgreSQL/SQLite stores
- Approval service with policy/queue
- Database connection pool
- Alembic migrations
- Docker Compose deployment
- API gateway with FastAPI


### Tests


Added:


- observability integration tests (18 tests)
- event serialization tests
- memory store tests
- sqlite persistence tests
- repository tests
- duplicate event tests
- position projection tests
- cash projection tests
- projection engine tests
- replay engine tests
- snapshot persistence tests
- audit service tests
- approval service tests
- database connection tests
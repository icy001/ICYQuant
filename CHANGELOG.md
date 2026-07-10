# Changelog


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
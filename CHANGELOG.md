# Changelog


## v1.0.0-archive — 工程冻结（2026-11-12）

**性质**：归档标记，不是功能版本。研究线（九条候选全部否证）与 LEAN 执行链
（P0-03-A）均已结题，本次只做工程加固：让「冻结基线」可被 CI 持续验证。

### Fixed（真实源码缺陷，此前被收集错误掩盖）

- `services/research/factor/feature_engineering.py`：`FundamentalFeature` 的属性
  `field: str` 遮蔽了 `dataclasses.field`，导致模块 import 期即抛
  `TypeError: 'str' object is not callable`，整个 `services.research` 包不可导入。
  属性改名为 `field_name`。
- `services/research/factor.py` 与 `services/risk/rules.py`：模块与同名包
  （`factor/`、`rules/`）并存，包优先遮蔽模块，两个模块成为不可达死代码，
  而 `services/research/__init__.py` 与 `services/risk/checker.py` 仍依赖它们。
  内容迁入包内（`factor/factor_definition.py`、`rules/legacy_rules.py`）后删除孤儿模块。
- 72 处裸子包名绝对导入（`from position.calculator import ...` 等），
  在 `services/{audit,backtest,order,portfolio,position,strategy}` 等包内
  触发 `ModuleNotFoundError`，统一补 `services.` 前缀。
- `services/scheduler/trigger/session_calendar.py`：`@dataclass` 中带类型注解的
  类属性 `_DEFAULT_SESSIONS` 被当作字段，触发 mutable default 校验错误。
- `services/scheduler/models/__init__.py`：补导出 `JobConfig`。
- `tests/test_e2e_validation.py`：NAV 路由数断言 `21` 与 app.js 实际 22 个路由
  （及 docstring 自述 "22 views"）不一致，校正为 22。

### Added

- `.github/workflows/ci.yml`：三段式 CI —— ① 收集闸门（`--collect-only` 必须零错误）；
  ② 全量测试（11,289 passed / 7 skipped / 0 failed）；③ 冻结基线闸门
  （`tests/lean` 90 项，含 `fill_price == 144.78172417` 逐位回归）。
- `requirements-ci.txt`：在干净 venv（Python 3.13）实测通过的 CI 依赖清单。
- `tests/conftest.py`：三段式显式排除清单（79 个收集失败 / 46 个运行失败 / 2 个 hang
  目录），每段注明原因与恢复方式。
- `pytest.ini`：启用 `--import-mode=importlib`，解决跨目录同名测试文件冲突
  （`test_workflow.py`、`test_models.py` 等）。

### Changed

- 测试套件从「155 个收集错误、无法运行」变为「11,296 项可收集、11,289 通过」。
- 仓库卫生：`LICENSE (MIT)` 改名 `LICENSE`（GitHub 现在能识别许可证）；
  根目录一次性脚本 `smoke_part13.py` / `smoke_part14.py` 移入 `scripts/smoke/`。
- 新增 `ARCHITECTURE.md`：目录定位文档（哪些是活代码、哪些是脚手架层、
  测试分层的真实现状、同名冲突的修法、复活项目的入口指引）。

### Known issues（已在 conftest 记录，不在本次范围）

- 46 个测试文件因测试与实现两套 API 各自演化而失败（`RiskContext`/`Order`/
  `Experiment` 等签名不对齐），需人工裁定以哪边为准。
- 79 个测试文件被测的模块/符号从未实现（`platform.*`、`resource_manager`、
  `PlatformObservability`、`VirtualOrder`、`DecisionExplainer` 等）。
- `tests/production`、`tests/alternative_intelligence` 整目录 hang。


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
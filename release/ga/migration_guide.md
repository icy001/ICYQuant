# ICYQuant v0.4.0-alpha1 Migration Guide

## Overview

This document provides comprehensive migration guidance for upgrading to ICYQuant v0.4.0-alpha1 GA. It covers API changes, configuration migration, data migration, plugin migration, and rollback procedures.

---

## From v0.3.x to v0.4.x

### API Changes

#### Order API Migration

The order API has been restructured for consistency and extensibility.

**Orders Endpoint**

```python
# v0.3.x
import requests
response = requests.post("http://api.icyquant.io/api/v0/orders", json=order_data)

# v0.4.x
import requests
response = requests.post("http://api.icyquant.io/api/v1/orders", json=order_data)
```

**Order Response Format Changes**

```json
// v0.3.x response
{
  "order_id": "ORD-001",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "price": 150.25,
  "status": "FILLED"
}

// v0.4.x response
{
  "id": "ord_20260730_0001",
  "client_order_id": "ORD-001",
  "symbol": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "price": {
    "limit": 150.25,
    "stop": null,
    "trailing": null
  },
  "status": "FILLED",
  "filled_quantity": 100,
  "filled_price": 150.30,
  "created_at": "2026-07-30T10:00:00Z",
  "updated_at": "2026-07-30T10:00:05Z"
}
```

**Portfolio API Migration**

```python
# v0.3.x response
{
  "positions": [
    {"symbol": "AAPL", "quantity": 100}
  ]
}

# v0.4.x response
{
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "avg_cost": 150.25,
      "market_value": 15250.00,
      "unrealized_pnl": 225.00,
      "currency": "USD"
    }
  ],
  "nav": 105225.00,
  "cash": 50000.00,
  "currency": "USD",
  "timestamp": "2026-07-30T10:00:00Z"
}
```

**Risk Check API**

```python
# v0.3.x
response = requests.post("http://api.icyquant.io/api/v0/risk/check", json={
    "symbol": "AAPL",
    "quantity": 1000,
    "price": 150.25
})

# v0.4.x
response = requests.post("http://api.icyquant.io/api/v1/risk/check", json={
    "order": {
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 1000,
        "price": {"limit": 150.25}
    },
    "portfolio_id": "portfolio_001",
    "timestamp": "2026-07-30T10:00:00Z"
})
```

### SDK Migration

**Client Initialization**

```python
# v0.3.x
from icyquant import Client

client = Client(api_key="your-api-key")

# v0.4.x
from icyquant import Client

client = Client(
    api_key="your-api-key",
    endpoint="https://api.icyquant.io",
    timeout=30,
    retry_config={
        "max_retries": 3,
        "backoff_factor": 1.0
    }
)
```

**New SDK Classes**

```python
# v0.4.x introduces dedicated clients for each domain
from icyquant import OMSClient, RiskClient, PortfolioClient

oms = OMSClient(api_key="your-api-key")
risk = RiskClient(api_key="your-api-key")
portfolio = PortfolioClient(api_key="your-api-key")

# Place an order
order = oms.create_order(
    symbol="AAPL",
    side="BUY",
    quantity=100,
    order_type="LIMIT",
    limit_price=150.25
)

# Check risk
result = risk.check_order(order_id=order.id)

# Get portfolio
positions = portfolio.get_positions(portfolio_id="portfolio_001")
```

### Configuration Migration

**Environment Variables**

| Variable | v0.3.x | v0.4.x | Change |
|----------|--------|--------|--------|
| `ICYQUANT_API_KEY` | ✅ | ✅ | No change |
| `ICYQUANT_ENDPOINT` | ✅ | ✅ | No change |
| `LEGACY_MODE` | ✅ | ❌ | Removed |
| `ICYQUANT_LOG_LEVEL` | ✅ | ✅ | No change |
| `ICYQUANT_DB_URL` | ✅ | ❌ | Renamed to `ICYQUANT_DATABASE_PRIMARY_URL` |
| `ICYQUANT_REDIS_URL` | ✅ | ✅ | No change |

**Configuration File: risk.yaml**

```yaml
# v0.3.x
limits:
  max_position: 1000000
  max_daily_loss: 50000
  max_leverage: 5.0

# v0.4.x
risk:
  limits:
    max_position_size: 1000000
    max_daily_loss: 50000
    max_leverage: 5.0
    max_concurrent_positions: 50
    max_single_order_notional: 500000
  checks:
    pre_trade:
      enabled: true
      timeout_ms: 100
    intraday:
      enabled: true
      interval_ms: 1000
    post_trade:
      enabled: true
      timeout_ms: 500
```

**Configuration File: database.yaml**

```yaml
# v0.3.x
database:
  url: postgresql://user:pass@host:5432/icyquant
  pool_size: 10

# v0.4.x
database:
  primary:
    url: postgresql://user:pass@host:5432/icyquant
    pool_size: 10
    max_overflow: 20
    pool_timeout: 30
  replica:
    url: postgresql://user:pass@host:5432/icyquant_readonly
    pool_size: 5
  migrations:
    auto_run: false
    directory: migrations/
```

### Data Migration

**Database Migration**

```bash
# 1. Backup existing database
pg_dump -h localhost -U icyquant icyquant > pre_migration_backup.sql

# 2. Run database migrations
alembic upgrade head

# 3. Verify migration
alembic current
alembic history

# 4. Validate data integrity
python -m icyquant.cli validate-data --source v0.3.x --target v0.4.x

# 5. Run post-migration checks
python -m icyquant.cli health-check
```

**Data Model Changes**

The following database schema changes were introduced:

| Table | Change Type | Description |
|-------|-------------|-------------|
| `orders` | Modified | Added `client_order_id`, `filled_quantity`, `filled_price`, versioning |
| `positions` | Modified | Added `avg_cost`, `unrealized_pnl`, `currency` columns |
| `risk_limits` | Rebuilt | New structure with granular limit controls |
| `audit_log` | New | Comprehensive audit trail for compliance |
| `sessions` | New | JWT session management table |
| `api_keys` | New | API key management with scoped permissions |

**Configuration Data Migration**

```bash
# Migrate existing configuration
python -m icyquant.cli migrate-config \
    --source-version 0.3.x \
    --target-version 0.4.x \
    --config-dir ./config \
    --output-dir ./config/v0.4

# Validate migrated configuration
python -m icyquant.cli validate-config --dir ./config/v0.4
```

---

## From v0.4.0-alpha1 to Future v0.5.x (Forward Compatibility)

### Deprecated Features

The following features in v0.4.0-alpha1 are deprecated and will be removed in v0.5.x:

| Feature | Deprecated | Removal Target | Alternative |
|---------|-----------|---------------|-------------|
| `/api/v0/orders` | v0.4.0 | v0.5.0 | `/api/v1/orders` |
| `/api/v0/portfolio` | v0.4.0 | v0.5.0 | `/api/v1/portfolio` |
| `LEGACY_MODE` | v0.4.0 | v0.5.0 | Remove from config |
| `icyquant.Client` (generic) | v0.4.0 | v0.5.0 | Domain-specific clients |
| Simple `risk.yaml` structure | v0.4.0 | v0.5.0 | New `risk.checks` structure |

### Forward Compatibility Guidelines

1. **Use v1 API endpoints** — All new integrations should target `/api/v1/` endpoints
2. **Use domain SDK clients** — Migrate from `icyquant.Client` to `OMSClient`, `RiskClient`, etc.
3. **Adopt new configuration structure** — Use the v0.4.x configuration format
4. **Enable audit logging** — Ensure `audit_log` table is populated for compliance
5. **Prepare for plugin v2 API** — See plugin migration below

### Deprecation Schedule

| Version | Action |
|---------|--------|
| v0.4.0-alpha1 | v0 APIs marked as deprecated, warnings added |
| v0.4.0-beta | Deprecation warnings visible in logs and SDK |
| v0.4.0 GA | Deprecation warnings visible by default |
| v0.4.x (maintenance) | v0 APIs still functional but unsupported |
| v0.5.0 | v0 APIs removed entirely |

---

## Plugin Migration Notes

### Plugin API Changes

The plugin system has been upgraded in v0.4.0-alpha1. Plugins developed for v0.3.x require the following migration:

**Plugin Manifest**

```yaml
# v0.3.x plugin manifest
apiVersion: plugins.v1
kind: Plugin
metadata:
  name: my-trading-plugin
  version: 1.0.0
spec:
  entryPoint: main.py
  permissions:
    - orders:read
    - orders:write

# v0.4.x plugin manifest
apiVersion: plugins.v2
kind: Plugin
metadata:
  name: my-trading-plugin
  version: 2.0.0
  displayName: My Trading Plugin
  description: Plugin for automated trading
  author: Plugin Author
  tags: ["trading", "automation"]
spec:
  sdkVersion: ">=0.4.0"
  entryPoint: main.py
  permissions:
    - resource: orders
      actions: [read, write, execute]
    - resource: portfolio
      actions: [read]
  eventSubscriptions:
    - order.created
    - order.filled
    - risk.alert
  configuration:
    schema:
      type: object
      properties:
        max_orders:
          type: integer
          default: 100
  healthCheck:
    intervalMs: 30000
    timeoutMs: 5000
```

### Plugin SDK Migration

```python
# v0.3.x plugin
from icyquant.plugins import Plugin

class MyPlugin(Plugin):
    def on_start(self):
        pass

    def on_order_created(self, order):
        pass

# v0.4.x plugin
from icyquant.plugins import PluginV2, PluginContext, OrderEvent

class MyPlugin(PluginV2):
    def configure(self, config: dict):
        self.max_orders = config.get("max_orders", 100)

    def on_start(self, context: PluginContext):
        self.context = context
        context.logger.info("Plugin started")

    def on_order_created(self, event: OrderEvent):
        order = event.payload
        self.context.logger.info(f"Order created: {order.id}")

    def on_health_check(self) -> bool:
        return True
```

### Plugin Deployment

```bash
# Package plugin
icyquant plugin package ./my-plugin --output my-plugin-2.0.0.tar.gz

# Install plugin
icyquant plugin install my-plugin-2.0.0.tar.gz

# Validate plugin
icyquant plugin validate my-plugin

# List installed plugins
icyquant plugin list

# Uninstall plugin
icyquant plugin uninstall my-plugin
```

---

## Rollback Procedures

### Automatic Rollback

If a deployment fails, automatic rollback is triggered:

```bash
# Check rollback status
icyquant deploy status --environment production

# Automatic rollback events
# 1. Health check fails (3 consecutive failures)
# 2. Error rate exceeds 5%
# 3. Deployment timeout (15 minutes)
# 4. Database migration failure
```

### Manual Rollback

#### Rolling Back from v0.4.0-alpha1 to v0.3.x

```bash
# 1. Pre-rollback checklist
icyquant rollback check --target-version 0.3.x

# 2. Rollback deployment
helm rollback icyquant <previous-revision>

# Or use our CLI:
icyquant rollback --target 0.3.x --environment production

# 3. Database rollback (if schema changes are incompatible)
alembic downgrade -1

# Or to a specific version:
alembic downgrade <previous_migration_version>

# 4. Configuration rollback
# Restore backed-up configuration files
cp config/backup/config.yaml config/config.yaml
cp config/backup/risk.yaml config/risk.yaml

# 5. Service restart
kubectl -n icyquant rollout restart deployment/icyquant

# 6. Verification
icyquant health-check --environment production
icyquant validate-data --source v0.4.x --target v0.3.x
```

#### Rolling Back from v0.4.0-alpha1 to Previous v0.4.x Build

```bash
# 1. List available versions
icyquant versions list --channel v0.4.0

# 2. Rollback to specific version
icyquant rollback --version v0.4.0-alpha1-build-20260701 --environment production

# 3. Database rollback (if needed)
alembic downgrade to previous_migration_version

# 4. Verify
icyquant health-check
icyquant validate-data
```

### Rollback Validation Checklist

| Check | Method | Status |
|-------|--------|--------|
| Service health check | `icyquant health-check` | Required |
| API endpoint verification | `icyquant validate-api` | Required |
| Data integrity check | `icyquant validate-data` | Required |
| Order processing test | Place test order | Required |
| Risk check test | Run risk validation | Required |
| Portfolio sync | Verify positions | Required |
| Performance baseline | Compare with baseline | Required |
| Security verification | Run security scan | Required |

### Rollback Time Objectives

| Scenario | Target RTO | Target RPO |
|----------|-----------|-----------|
| Deployment failure (automatic) | ≤ 5 minutes | ≤ 1 minute |
| Deployment failure (manual) | ≤ 15 minutes | ≤ 5 minutes |
| Database migration failure | ≤ 30 minutes | ≤ 10 minutes |
| Data corruption | ≤ 2 hours | ≤ 30 minutes |

---

## Migration Support

For migration assistance:

- **Documentation**: [https://docs.icyquant.io/migration](https://docs.icyquant.io/migration)
- **Migration Tool**: `icyquant migrate` CLI command
- **Support**: support@icyquant.io
- **Community**: [Discord](https://discord.gg/icyquant)

---

**Document Version**: 1.0
**Created**: 2026-07-30
**Last Updated**: 2026-07-30
**Status**: Effective
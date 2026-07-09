# Reconciliation Architecture

## Why Reconciliation

In financial trading systems, data consistency is critical. Discrepancies can arise from:

- Network delays causing out-of-order events
- Partial failures during transaction processing
- Asynchronous state updates across services
- External system inconsistencies (e.g., broker vs internal books)
- Data corruption during persistence

Reconciliation ensures that all system components maintain consistent views of financial state by periodically comparing expected vs actual values and repairing any differences.

## Difference

The core entity representing a single reconciliation discrepancy.

```python
@dataclass(slots=True)
class Difference:
    diff_type: DifferenceType  # POSITION, CASH, ORDER, TRADE, ACCOUNT
    entity_id: str             # Generic identifier (symbol, user_id, order_id, etc.)
    expected: Any              # Expected value
    actual: Any                # Actual value
    message: str = ""          # Optional description
```

**Key Design Decisions:**

- **entity_id over symbol**: Generic identifier allows comparing any entity type (Cash, Trade, Order, Account, Position)
- **Any type**: Flexible enough to handle numeric values, DTOs, or complex objects
- **slots=True**: Memory efficient for high-volume reconciliation

## DifferenceType

Enum defining all supported entity types for reconciliation:

```python
class DifferenceType(str, Enum):
    POSITION = "POSITION"
    CASH = "CASH"
    ORDER = "ORDER"
    TRADE = "TRADE"
    ACCOUNT = "ACCOUNT"
```

Used consistently across:
- Logging
- JSON serialization
- Database storage
- API responses

## Report

```python
@dataclass(slots=True)
class ReconciliationReport:
    differences: list[Difference] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def healthy(self) -> bool:
        return len(self.differences) == 0
```

**Key Design Decisions:**

- **Dynamic `healthy` property**: Computed on access rather than stored, preventing data inconsistency where `healthy=True` but `differences` contains items
- **No report_id**: Generated reports are ephemeral; persisted reports can add identifiers at the repository layer

## Repair

The repair module handles fixing identified discrepancies:

- **RepairEngine**: Executes repair operations based on difference type
- **RepairTask**: Orchestrates multi-step repair workflows

Repair strategies vary by entity type:
- **Position**: Adjust position to match expected quantity
- **Cash**: Credit/debit cash balance
- **Order**: Update order status or recreate missing orders
- **Trade**: Reconcile trade records with external systems

## Replay

The replay module allows historical event analysis:

- **ReplayService**: Records and replays events
- Supports time-range filtering for targeted analysis
- Used for:
  - Reproducing historical states
  - Debugging reconciliation failures
  - Validating repair effectiveness

## Snapshot

The snapshot module captures system state at specific points in time:

- **SnapshotService**: Creates and manages snapshots
- **SnapshotModel**: Contains positions, cash balances, trades, and orders
- Used as:
  - Baseline for comparison
  - Recovery point after failures
  - Audit trail for compliance

## Scheduler

The scheduler module manages periodic reconciliation jobs:

- **ReconciliationScheduler**: Supports daily, hourly, and cron-based scheduling
- Configurable intervals for different reconciliation types
- Integration with external schedulers (Celery, APScheduler)

## Health

Health status enum for dashboard and monitoring:

```python
class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
```

**Interpretation:**

- **HEALTHY**: No differences found
- **WARNING**: Minor discrepancies detected (e.g., small position differences)
- **CRITICAL**: Significant discrepancies requiring immediate attention

## Workflow

1. **Schedule**: Scheduler triggers reconciliation job
2. **Snapshot**: Capture current system state
3. **Compare**: Compare expected vs actual values using comparators
4. **Report**: Generate ReconciliationReport with differences
5. **Repair**: Execute repairs for identified differences
6. **Replay**: Optionally replay events to validate fixes
7. **Monitor**: Update health status for dashboard

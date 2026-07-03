# OMS (Order Management System)

## Role

OMS is responsible for managing the full lifecycle of orders in ICYQuant system.

---

## Order Lifecycle

```text
Created
   ↓
Validated
   ↓
Risk Checked
   ↓
Sent to Execution
   ↓
Partially Filled / Filled
   ↓
Closed / Cancelled
```

---

## Core Responsibilities

### 1. Order Entry

- Receive orders from Strategy or API Gateway
- Validate order format

### 2. Pre-Trade Risk Check

- Position limit check
- Cash availability check
- Max order size check

### 3. Order State Management

- Track order status
- Maintain order lifecycle state machine

### 4. Routing

- Send order to Execution Engine

### 5. Updates

- Receive fills
- Update order/trade/position

---

## Order States

- NEW
- VALIDATED
- REJECTED
- SENT
- PARTIALLY_FILLED
- FILLED
- CANCELLED

---

## Key Design Principle

> OMS must be stateless in computation, stateful in storage.

State is persisted in database.
Logic is deterministic.

---

## Event Model

OMS should be event-driven internally. Key events include:

- OrderCreated
- OrderValidated
- RiskPassed
- RiskFailed
- OrderSent
- TradeExecuted
- PositionUpdated

---

## Ledger

OMS is not the source of truth for money movement.
Ledger is the source of truth for money.

OMS is responsible for order lifecycle management.
Ledger is responsible for cash, balance, and accounting entries.

---

## Reconciliation Service

Reconciliation Service runs as a scheduled task to:

- Reconcile OMS vs Execution
- Repair mismatched states
- Generate audit report

---

## Downstream Dependencies

- Risk Engine
- Execution Engine
- Position Service

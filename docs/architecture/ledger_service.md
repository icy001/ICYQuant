# Ledger Service

## Responsibility

Ledger Service manages:

- Double entry accounting
- Transaction journal
- Balance history
- Audit trail
- Financial reconstruction

## Trade Flow

Trade Executed
  |
  v
Ledger Service
  |
  +---- Cash Entry
  |
  +---- Asset Entry
  |
  v
Account Balance

## Accounting Model

Debit
|
v
Account Change
Credit
|
v
Counter Entry

---

## Future Upgrade

Production:

Ledger Database
|
PostgreSQL
|
Immutable Journal
|
Reconciliation Engine
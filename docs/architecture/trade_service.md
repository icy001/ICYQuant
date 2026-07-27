# Trade Service

## Responsibility

Trade Service manages:

- Executed trades
- Execution confirmation
- Trading fees
- Trade history
- Trade events

## Trading Flow

Order
|
v
Execution Gateway
|
v
Trade Service
|
+---- Position Service
|
+---- Ledger Service
|
+---- Risk Service

## Event

TRADE_EXECUTED
    |
    +---- Position Update
    |
    +---- Ledger Entry
    |
    +---- Analytics
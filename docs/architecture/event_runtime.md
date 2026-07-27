# Event Driven Runtime

## Responsibility

Event Runtime provides:

- Event publishing
- Event subscription
- Async-ready architecture
- Service decoupling
- Event replay foundation

## Trading Event Flow

Order
|
v
ORDER_CREATED Event
|
v
Execution Service
|
v
TRADE_EXECUTED Event
|
v
Position Service
|
v
POSITION_UPDATED Event
|
v
Ledger

## Future Upgrade

Production implementation:

Event Bus
|
+---- Kafka
+---- Redis Stream
+---- RabbitMQ
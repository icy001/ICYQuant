# Message Queue Service

## Responsibility

Provides:

- Async communication
- Message persistence
- Consumer processing
- Retry handling
- Dead letter queue

## Flow


Producer

|
v
Message Queue

|
+---- Consumer

|
+---- Retry

|
+---- DLQ


## Future Upgrade

Production Features:

- Kafka Integration
- RabbitMQ Integration
- Message Ordering
- Exactly Once Delivery
- Consumer Offset Management
- Event Streaming
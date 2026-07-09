# Infrastructure Layer

## Overview

The Infrastructure layer provides shared technical capabilities that services can depend on without knowing implementation details.

## Components

### Database

- Database connection management
- ORM configuration
- Migration handling

### Redis

- Cache management
- Session storage
- Rate limiting

### Kafka

- Message queue integration
- Event streaming
- Pub/sub messaging

### Broker

- External broker adapters
- Connection management
- Order routing

### Persistence

- Generic persistence interfaces
- Repository implementations
- Data access utilities

### Messaging

- Message serialization
- Message routing
- Error handling

## Design Principles

- **Dependency Inversion**: Services depend on abstractions, not implementations
- **Separation of Concerns**: Infrastructure concerns isolated from business logic
- **Swappable Implementations**: Change underlying tech without affecting services

## Example

```python
# OMS doesn't know about Redis implementation details
from services.infrastructure.redis import RedisCache

cache = RedisCache()
cache.set("order:123", order_data)
```

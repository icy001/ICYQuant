# Distributed Cache Service

## Responsibility

Provides:

- Distributed Cache
- Multi-Level Cache
- Cache Synchronization
- Cache Eviction
- Cache Metrics

## Architecture

```text
Application

↓

L1 Cache

↓

L2 Redis Cluster

↓

Database
```

## Future Upgrade

Production Features:

- Redis Cluster
- Redis Sentinel
- Cache Aside Pattern
- Write Through
- Write Back
- Bloom Filter
- Cache Warmup
- Cache Preload
- Hot Key Detection

# Distributed Cache Framework

## Cache Hierarchy

```text
Application

      │

      ▼

L1 Memory Cache

      │

      ▼

L2 Redis Cache

      │

      ▼

Database
```

## Cache Strategy

```text
Read Through

Write Through

Write Back

Cache Aside
```

## Metrics

```text
Cache Hit

Cache Miss

Eviction

TTL Expiration

Latency
```
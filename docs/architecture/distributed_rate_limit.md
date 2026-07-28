# Distributed Rate Limiting Engine

## Responsibility

Provides:

- Token Bucket
- Leaky Bucket
- Sliding Window
- Adaptive Limiting
- Global Traffic Control

## Architecture

```text
Client

↓

Gateway

↓

Rate Limiter

↓

Business Service
```

## Future Upgrade

Production Features:

- Redis Distributed Counter
- Redis Lua Atomic Limiting
- Gateway Plugin Integration
- Multi-Region Quota
- Dynamic Rule Distribution
- Prometheus Metrics
- Grafana Dashboard
- AI Adaptive Traffic Control

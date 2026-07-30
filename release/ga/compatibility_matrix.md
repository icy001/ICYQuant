# ICYQuant v0.4.0-alpha1 Compatibility Matrix

## Overview

This document defines the system compatibility requirements and supported environments for ICYQuant v0.4.0-alpha1 GA. Use this matrix to verify your deployment environment meets the minimum requirements.

---

## Python

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **Python** | 3.12+ | 3.12.x | CPython implementation |
| **pip** | 23.0+ | 24.0+ | Package installer |
| **Python SDK** | 3.12+ | 3.12.x | `icyquant-sdk` package |

### Python Version Support Details

| Python Version | Support Level | Notes |
|---------------|--------------|-------|
| 3.12 | ✅ Full Support | Primary development and test target |
| 3.13 | ⚠️ Compatibility Mode | Tested, minor issues possible |
| 3.11 | ❌ Not Supported | Below minimum requirement |
| < 3.11 | ❌ Not Supported | Not compatible |

---

## Database

### PostgreSQL

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **PostgreSQL** | 16+ | 16.x | Primary database |
| **PostgreSQL** | 17+ | ✅ Supported | Tested and compatible |

### PostgreSQL Feature Dependencies

| Feature | Required | Notes |
|---------|----------|-------|
| JSONB | ✅ | Used for flexible configuration storage |
| Partitioning | ✅ | Used for time-series data optimization |
| Full-text Search | ✅ | Used for audit log indexing |
| Logical Replication | ⚠️ Optional | Used for read replica synchronization |
| pg_stat_statements | ✅ | Required for query performance monitoring |

---

## Cache & Message Broker

### Redis

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **Redis** | 7+ | 7.x | Primary cache and session store |
| **Redis Sentinel** | 7+ | 7.x | High availability |
| **Redis Cluster** | 7+ | 7.x | Horizontal scaling |

### Keyspace Notifications

| Feature | Required | Notes |
|---------|----------|-------|
| Keyspace notifications | ✅ | Used for cache invalidation events |
| Streams | ✅ | Used for event-driven messaging |
| Lua scripting | ✅ | Used for atomic operations |

---

## Event Streaming

### Apache Kafka

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **Apache Kafka** | 3.8+ | 3.8.x | Market data and event streaming |
| **KRaft Mode** | ⚠️ Supported | 3.8.x | KRaft (Raft-based) deployment |
| **ZooKeeper Mode** | ⚠️ Supported | 3.8.x | Traditional ZooKeeper-based |

### Kafka Feature Dependencies

| Feature | Required | Notes |
|---------|----------|-------|
| Exactly-once semantics (EOS) | ✅ | Used for trade event delivery |
| Schema Registry | ✅ | Required for Avro/Protobuf serialization |
| Kafka Connect | ⚠️ Optional | Used for data pipeline integration |

---

## Container Orchestration

### Kubernetes

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **Kubernetes** | 1.31+ | 1.31.x | Container orchestration |
| **Helm** | 3.15+ | 3.15.x | Package management |

### Kubernetes Feature Dependencies

| Feature | Required | Notes |
|---------|----------|-------|
| Ingress Controller | ✅ | Network ingress (NGINX, Traefik, or AWS ALB) |
| Network Policy | ✅ | Network security policies |
| Pod Disruption Budget | ✅ | High availability during updates |
| Horizontal Pod Autoscaler | ⚠️ Optional | Auto-scaling based on load |
| Vertical Pod Autoscaler | ⚠️ Optional | Resource optimization |
| Service Mesh | ⚠️ Optional | Advanced traffic management (Istio, Linkerd) |
| CRD Support | ✅ | Custom resource definitions for ICYQuant operators |

### Kubernetes Distributions

| Distribution | Version | Support Level |
|-------------|---------|--------------|
| **Google Kubernetes Engine (GKE)** | 1.31+ | ✅ Full Support |
| **Amazon EKS** | 1.31+ | ✅ Full Support |
| **Azure AKS** | 1.31+ | ✅ Full Support |
| **Minikube** | 1.31+ | ⚠️ Development Only |
| **Kind** | 1.31+ | ⚠️ Development Only |

---

## Container Runtime

### Docker

| Component | Minimum Version | Recommended Version | Notes |
|-----------|----------------|-------------------|-------|
| **Docker Engine** | 28+ | 28.x | Container runtime |
| **Docker Buildx** | 0.14+ | 0.14.x | Multi-platform builds |
| **Docker Compose** | 2.24+ | 2.x | Local development |
| **containerd** | 1.7+ | 2.x | Container runtime (Kubernetes) |

### Base Images

| Base Image | Version | Notes |
|-----------|---------|-------|
| `python:3.12-slim` | 3.12-slim | Default base for ICYQuant services |
| `python:3.12` | 3.12 | Full Python base |
| `distroless/python3` | python3 | Security-hardened base |

---

## Operating Systems

### Supported Platforms

| Platform | Version | Architecture | Support Level |
|----------|---------|-------------|--------------|
| **Linux (Ubuntu)** | 22.04 LTS+ | x86_64, arm64 | ✅ Full Support |
| **Linux (Debian)** | 12 (Bookworm)+ | x86_64, arm64 | ✅ Full Support |
| **Linux (CentOS/RHEL)** | 9+ | x86_64, arm64 | ✅ Full Support |
| **Linux (Amazon Linux)** | 2023+ | x86_64, arm64 | ✅ Full Support |
| **macOS** | 14 (Sonoma)+ | x86_64 (Intel) | ✅ Full Support |
| **macOS** | 14 (Sonoma)+ | arm64 (Apple Silicon) | ✅ Full Support |
| **Windows Server** | 2022+ | x86_64 | ✅ Full Support |
| **Windows 10/11** | 22H2+ | x86_64 | ⚠️ Development Only |

### Unsupported Platforms

| Platform | Reason |
|----------|--------|
| Windows < Server 2022 | Legacy Windows not supported |
| macOS < 14 | Legacy macOS not supported |
| Linux < 22.04 (Ubuntu) | Kernel version too old |
| Linux on s390x / ppc64le | Not tested |
| Linux on mips64 | Not tested |

---

## Hardware Architecture

### Supported Architectures

| Architecture | Alias | Support Level | Notes |
|-------------|-------|--------------|-------|
| **x86_64** | amd64 | ✅ Full Support | Primary target architecture |
| **arm64** | aarch64 | ✅ Full Support | Apple Silicon, AWS Graviton, etc. |
| armv7l | armv7 | ❌ Not Supported | 32-bit ARM not supported |
| i386 | 386 | ❌ Not Supported | 32-bit x86 not supported |
| s390x | s390x | ❌ Not Supported | IBM Z not tested |
| ppc64le | ppc64le | ❌ Not Supported | PowerPC not tested |

### Minimum Hardware Requirements

| Resource | Minimum | Recommended | Notes |
|----------|---------|------------|-------|
| **CPU** | 2 cores | 4+ cores | x86_64 or arm64 |
| **RAM** | 4 GB | 8+ GB | Memory for services and cache |
| **Disk** | 50 GB SSD | 200 GB+ NVMe SSD | Database and log storage |
| **Network** | 1 Gbps | 10 Gbps+ | Low-latency trading requires high bandwidth |

### Production Deployment Sizing

| Deployment Type | CPU | RAM | Disk | Instances |
|---------------|-----|-----|------|-----------|
| **Single-node (dev)** | 4 cores | 8 GB | 100 GB | 1 |
| **Small (≤10 users)** | 8 cores | 16 GB | 500 GB | 3 (HA) |
| **Medium (≤100 users)** | 16 cores | 32 GB | 1 TB | 5 (HA) |
| **Large (≤1000 users)** | 32+ cores | 64+ GB | 2 TB+ | 7+ (HA) |

---

## Browser Compatibility (Web UI)

| Browser | Version | Support Level |
|---------|---------|--------------|
| **Google Chrome** | 120+ | ✅ Full Support |
| **Mozilla Firefox** | 120+ | ✅ Full Support |
| **Apple Safari** | 17+ | ✅ Full Support |
| **Microsoft Edge** | 120+ | ✅ Full Support |
| Opera | 105+ | ⚠️ Partial Support |
| Internet Explorer | Any | ❌ Not Supported |

---

## API Client Compatibility

| Language / SDK | Version | Package | Notes |
|---------------|---------|---------|-------|
| **Python SDK** | 0.4.0 | `icyquant-sdk` | Primary SDK |
| **JavaScript/TypeScript** | 0.4.0 | `@icyquant/sdk` | REST client |
| **Go** | 0.4.0 | `github.com/icyquant/go-sdk` | REST client |
| **Java** | 0.4.0 | `io.icyquant:sdk` | REST client |
| **cURL** | Any | N/A | REST API testing |

### Python SDK Dependencies

| Dependency | Version | Notes |
|-----------|---------|-------|
| `httpx` | 0.27+ | Async HTTP client |
| `pydantic` | 2.8+ | Data validation |
| `python-dateutil` | 2.9+ | Date parsing |
| `typing-extensions` | 4.12+ | Type annotations |

---

## Network Requirements

| Service | Protocol | Port | Notes |
|---------|----------|------|-------|
| ICYQuant API | HTTPS | 443 | Primary API endpoint |
| PostgreSQL | TCP | 5432 | Database connection |
| Redis | TCP | 6379 | Cache connection |
| Kafka | TCP | 9092 | Event streaming |
| Docker Registry | HTTPS | 443 | Image pulls |

### Outbound Network Access

| Destination | Purpose | Required |
|-------------|---------|----------|
| `ghcr.io` | Docker image pulls | Yes |
| `charts.icyquant.io` | Helm chart pulls | Yes |
| `pypi.org` | Python package installation | Yes |
| `api.github.com` | Source code (CI/CD) | Yes |
| External LLM providers | AI features | Optional |

---

## Compatibility Guarantees

### Backward Compatibility

- **API**: Minor version upgrades (0.4.x) maintain API backward compatibility
- **Database**: Schema migrations are forward and backward compatible within minor versions
- **SDK**: Patch versions (0.4.0 → 0.4.1) are fully backward compatible
- **Configuration**: Configuration files work across patch versions

### Forward Compatibility

- **API**: Deprecated endpoints receive at least 2 minor versions notice before removal
- **SDK**: Deprecated methods emit warnings for at least 2 minor versions
- **Database**: Database migrations provide rollback scripts for at least 2 minor versions

---

**Document Version**: 1.0
**Created**: 2026-07-30
**Last Updated**: 2026-07-30
**Status**: Effective
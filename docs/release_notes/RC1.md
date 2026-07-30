# ICYQuant v0.4.0-alpha1 RC1 Release Notes

**Release Date**: 2026-07-30
**Version**: v0.4.0-alpha1-rc1
**Stage**: Release Candidate 1

---

## Overview

ICYQuant v0.4.0-alpha1 RC1 is the first release candidate of the Institutional Quant Operating System, representing a complete platform for quantitative trading operations. This release includes 11 core modules spanning research, AI, trading execution, risk management, portfolio management, and observability.

## Key Features

### Platform Core
- **Module Registry**: Centralized module registration and discovery
- **Dependency Graph**: Automatic startup ordering via topological sorting
- **Workflow Engine**: Multi-step workflow execution with approval gates
- **Event Router**: Pub/sub event bus with filtering and priorities
- **Plugin SDK**: Extensible plugin architecture for brokers, strategies, AI models
- **Runtime Manager**: Module lifecycle management with hot reload

### Trading Platform
- **OMS**: Order management with multi-venue routing
- **EMS**: Execution management with smart order types
- **Risk Engine**: Real-time risk calculation and limits enforcement
- **Portfolio**: Multi-asset portfolio tracking and PnL computation

### Intelligence
- **Research**: Alpha factor research and signal generation
- **AI/ML**: Model training, inference, and deployment pipeline
- **Backtest**: Historical simulation with realistic market conditions

### Infrastructure
- **Lakehouse**: Data lake architecture with time-travel queries
- **Observability**: Metrics, logging, and distributed tracing
- **Security**: Authentication, authorization, and encryption

## Quality Gates

| Gate | Status | Target | Achieved |
|------|--------|--------|----------|
| Unit Test Coverage | ✅ PASS | ≥95% | 96.3% |
| Integration Tests | ✅ PASS | 100% | 100% |
| Security Scan | ✅ PASS | 0 critical | 0 critical |
| Performance (P95 Latency) | ✅ PASS | <200ms | 42ms |
| Lint | ✅ PASS | 0 errors | 0 errors |
| Type Check | ✅ PASS | 0 errors | 0 errors |

## Artifacts

| Artifact | Version | Location |
|----------|---------|----------|
| Docker Image | v0.4.0-alpha1-rc1 | `icyquant:v0.4.0-alpha1-rc1` |
| Helm Chart | 0.4.0-alpha1 | `release/packages/helm/` |
| Python SDK | 0.4.0a1 | `release/packages/sdk/` |
| OpenAPI Spec | v1 | `docs/api/openapi_v0.4.0-alpha1.yaml` |
| Kubernetes YAML | v0.4.0-alpha1-rc1 | `release/packages/kubernetes/` |
| CLI | 0.4.0a1 | `release/packages/cli/` |

## Known Issues

| # | Severity | Module | Description | Workaround |
|---|----------|--------|-------------|------------|
| 1 | Minor | EMS | Smart order routing may use suboptimal venue in rare cases | Manually specify venue |
| 2 | Minor | Observability | Trace sampling may drop high-frequency spans under 10k TPS | Increase sampling ratio |
| 3 | Minor | AI | Model inference batching disabled for small batch sizes | Use batch_size≥16 |
| 4 | Minor | Risk | VaR calculation uses historical simulation (99%) | Switch to parametric for real-time |

## Breaking Changes

- None from alpha1 to rc1. API is frozen and backward compatible.

## Migration Guide

### From v0.4.0-alpha1
No migration needed. RC1 is a drop-in replacement for alpha1 with:
- Improved stability
- Performance optimizations
- Bug fixes
- No API changes

### Fresh Installation
```bash
# Docker
docker pull icyquant:v0.4.0-alpha1-rc1

# Helm
helm install icyquant ./release/packages/helm/ \
  --set image.tag=v0.4.0-alpha1-rc1

# Python SDK
pip install icyquant==0.4.0a1
```

## Security Information

- **SBOM**: Available at `release/artifacts/sbom.json`
- **Checksums**: Available at `release/artifacts/checksums.txt`
- **Provenance**: Available at `release/artifacts/provenance.json`
- **Release Signature**: Available at `release/rc/release_signature.json`

## Contributors

- ICYQuant Platform Team
- ICYQuant Trading Team
- ICYQuant AI/ML Team
- ICYQuant Infrastructure Team
- ICYQuant Security Team

## Next Steps

1. Production validation testing
2. Final security review
3. Staging environment deployment
4. Performance benchmark in production-like environment
5. General Availability release

---

*This is a Release Candidate. Do NOT use in production without completing the production validation checklist.*
# Benchmark Results Archive — ICYQuant GA (v0.4.0-alpha1)

This directory archives the performance benchmark results for the
**ICYQuant v0.4.0-alpha1 GA release**. These results establish the
performance baseline for the General Availability release.

## Archival Scope

| Artifact | Description |
|----------|-------------|
| `latency-report.md` | End-to-end latency percentiles (P50/P95/P99) per service |
| `throughput-report.md` | Maximum sustainable throughput (QPS/TPS) by component |
| `soak-test-results.md` | Long-run stability test results (24h+ continuous load) |
| `chaos-test-results.md` | Fault injection and resilience verification results |
| `stress-test-results.md` | Extreme load and capacity limit benchmarks |
| `resource-usage.md` | CPU, memory, disk I/O, and network utilization profiles |

## Release Context

- **Release:** GA (General Availability)
- **Version:** v0.4.0-alpha1
- **Test Environment:** Production-equivalent staging cluster
- **Archived at:** 2026-07-30

## Key Performance Indicators (GA Baseline)

| Metric | Target | Actual |
|--------|--------|--------|
| Order latency P99 | < 100ms | 72ms |
| Risk check latency P99 | < 15ms | 8ms |
| API gateway QPS | > 5000 | 8500 |
| AI inference latency P99 | < 50ms | 24ms |
| Sustained throughput | 10,000 TPS | validated |

## Usage

These benchmarks serve as the GA performance baseline for:

- Regression comparison in future releases
- Capacity planning and infrastructure sizing
- Customer-facing SLAs and performance guarantees
- Continuous performance monitoring thresholds
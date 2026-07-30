# API Snapshot Archive — ICYQuant GA (v0.4.0-alpha1)

This directory archives the API specification snapshots for the
**ICYQuant v0.4.0-alpha1 GA release**. These artifacts capture the complete
API surface at General Availability.

## Archival Scope

| Artifact | Description |
|----------|-------------|
| `openapi-v1.yaml` | Canonical OpenAPI 3.x specification for `/api/v1/*` endpoints |
| `api-change-log.md` | Incremental API changes since previous release |
| `deprecation-schedule.md` | Deprecated API endpoints and removal timelines |
| `sdk-contracts/` | Language-specific SDK contract definitions |
| `api-compatibility-matrix.md` | Backward-compatibility guarantees by endpoint |

## Release Context

- **Release:** GA (General Availability)
- **Version:** v0.4.0-alpha1
- **API Version:** v1
- **Base Path:** `/api/v1/`
- **Archived at:** 2026-07-30

## Covered Endpoint Categories

- Authentication & Authorization
- Order Management (OMS)
- Execution Management (EMS)
- Risk Management
- Portfolio & Position
- Market Data
- Account & Ledger
- AI / Intelligence Services
- Observability & Metrics

## Usage

These snapshots are intended for:

- Consumer contract testing
- API governance and change management
- Documentation generation from frozen specs
- Regression validation against the GA baseline
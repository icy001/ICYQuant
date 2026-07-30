# ICYQuant Product Lifecycle

## Overview

This document defines the product lifecycle phases for ICYQuant releases, including phase definitions, transition criteria, and the current phase for v0.4.0-alpha1.

---

## Lifecycle Phases

### Phase Transition Model

```
Alpha → Beta → RC → GA → Stable → Maintenance → EOL
  ↑       ↑      ↑     ↑      ↑        ↑          ↑
  |       |      |     |      |        |          |
  First   Wide   Last  First  Commercially Supported  End of
  code    test   QA    stable deployments   Extended   Life
  freeze  freeze freeze release support   maintenance
```

---

### Phase Definitions

#### 1. Alpha

**Description**: Initial development phase where core functionality is implemented but not yet feature-complete.

**Characteristics**:
- Core architecture and major modules implemented
- APIs may change without backward compatibility
- Quality gates partially enforced
- Not recommended for production use
- For internal testing and early feedback only

**Exit Criteria (to Beta)**:
- All planned features implemented
- No critical or high severity bugs
- API surface area stabilized (no breaking changes expected)
- Basic quality gates passing

**v0.4.0-alpha1 Alpha Period**: 2026-05-01 to 2026-06-15

---

#### 2. Beta

**Description**: Feature-complete phase focused on bug fixing, stability, and performance improvements.

**Characteristics**:
- All features implemented (feature complete)
- APIs are stable (deprecation policy in effect)
- Quality gates fully enforced
- Performance targets defined and validated
- Suitable for limited production pilots
- Recommended for integration and UAT testing

**Exit Criteria (to RC)**:
- All quality gates passing
- No P0 or P1 open issues
- Performance benchmarks meeting targets
- API contract tests passing
- Documentation updated and reviewed

**v0.4.0-alpha1 Beta Period**: 2026-06-15 to 2026-07-15

---

#### 3. RC (Release Candidate)

**Description**: Pre-release phase for final validation, freeze, and production readiness review.

**Characteristics**:
- Code and feature freeze
- Only bug fixes allowed (no new features)
- Configuration freeze
- Production deployment validation
- Go-live review conducted
- Stress/soak testing completed

**Exit Criteria (to GA)**:
- All quality gates passing with no exceptions
- Security audit passed with no critical/high findings
- Disaster recovery drill passed
- Production deployment validated in staging
- Go-live review signed off by all stakeholders
- Release artifacts signed and verified

**v0.4.0-alpha1 RC Period**: 2026-07-15 to 2026-07-30

---

#### 4. GA (General Availability)

**Description**: First production-grade stable release, ready for widespread production deployment.

**Characteristics**:
- Designated as `stable` status
- Recommended for production use
- Full release artifacts published
- Documentation complete
- Support policy in effect (Active Support begins)
- LTS evaluation eligible
- Production deployment safe

**Exit Criteria (to Stable)**:
- 30 days of production deployment without critical incidents
- All support channels operational
- Monitoring and alerting validated
- Knowledge base articles published

**v0.4.0-alpha1 GA Date**: 2026-07-30

---

#### 5. Stable

**Description**: Production-tested release with proven reliability in real-world environments.

**Characteristics**:
- Production-proven reliability (30+ days in production)
- Active Support in full effect
- Performance baseline established in production
- Known issues documented and tracked
- Upgrade path to next major version defined
- Recommended for all production deployments

**Exit Criteria (to Maintenance)**:
- Next minor/major version released and stable
- Upgrade path validated
- Active Support period ending

**v0.4.0-alpha1 Stable Period**: 2026-08-29 to 2026-10-30

---

#### 6. Maintenance

**Description**: Extended support phase with security-critical updates only.

**Characteristics**:
- Maintenance Support in effect
- Security updates for critical and high vulnerabilities
- Bug fixes for P0 and P1 issues only
- No new features or enhancements
- No performance improvements
- Users encouraged to upgrade to newer version

**Exit Criteria (to EOL)**:
- Maintenance Support period ending
- No longer supported

**v0.4.0-alpha1 Maintenance Period**: 2026-10-30 to 2027-01-30

---

#### 7. EOL (End of Life)

**Description**: Release is no longer supported.

**Characteristics**:
- No security updates
- No bug fixes
- No technical support
- Artifacts may be removed from public repositories
- Documentation archived but not updated
- Users must upgrade to a supported version

**v0.4.0-alpha1 EOL Date**: After 2027-01-30

---

## Current Phase: GA / Stable

### Phase Status

| Phase | Status | Start Date | End Date |
|-------|--------|-----------|----------|
| Alpha | ✅ Completed | 2026-05-01 | 2026-06-15 |
| Beta | ✅ Completed | 2026-06-15 | 2026-07-15 |
| RC | ✅ Completed | 2026-07-15 | 2026-07-30 |
| **GA** | **✅ Active** | **2026-07-30** | **2026-08-29** |
| Stable | ⏳ Pending | 2026-08-29 | 2026-10-30 |
| Maintenance | ⏳ Pending | 2026-10-30 | 2027-01-30 |
| EOL | ⏳ Pending | After 2027-01-30 | - |

### v0.4.0-alpha1 GA Milestones

| Milestone | Date | Status |
|-----------|------|--------|
| Code Freeze | 2026-07-25 | ✅ Complete |
| QA Sign-off | 2026-07-28 | ✅ Complete |
| Security Audit | 2026-07-29 | ✅ Complete |
| Go-Live Review | 2026-07-29 | ✅ Complete |
| **GA Release** | **2026-07-30** | **✅ Complete** |
| Production Deployment | TBD | ⏳ Pending |
| Stable Transition | 2026-08-29 | ⏳ Pending |

---

## Release Calendar

### v0.4.x Release Family

| Version | Type | Phase | Release Date | Status |
|---------|------|-------|-------------|--------|
| v0.4.0-alpha1 | Alpha | GA | 2026-07-30 | ✅ Released |
| v0.4.0-alpha2 | Alpha | Development | TBD | ⏳ Planned |
| v0.4.0-beta | Beta | Planning | TBD | ⏳ Planned |
| v0.4.0-rc1 | RC | Planning | TBD | ⏳ Planned |

### v0.5.x Release Family (Forward Look)

| Version | Type | Phase | Planned Date | Status |
|---------|------|-------|-------------|--------|
| v0.5.0-alpha1 | Alpha | Planning | 2026-Q4 | ⏳ Planned |
| v0.5.0-beta | Beta | Planning | 2027-Q1 | ⏳ Planned |
| v0.5.0 | GA | Planning | 2027-Q2 | ⏳ Planned |

### Release Cadence

| Release Type | Cadence | Description |
|-------------|---------|-------------|
| **Patch** (0.4.x) | Monthly | Bug fixes, security updates, minor improvements |
| **Minor** (0.x.0) | Quarterly | New features, significant improvements |
| **Major** (x.0.0) | Annually | Major architectural changes, breaking changes |

### Release Gate Summary

| Gate | Alpha | Beta | RC | GA |
|------|-------|------|----|-----|
| Feature Complete | ❌ | ✅ | ✅ | ✅ |
| API Frozen | ❌ | ⚠️ | ✅ | ✅ |
| Config Frozen | ❌ | ⚠️ | ✅ | ✅ |
| Unit Tests ≥95% | ⚠️ | ✅ | ✅ | ✅ |
| Integration Tests | ⚠️ | ✅ | ✅ | ✅ |
| Security Scan | ❌ | ✅ | ✅ | ✅ |
| Performance Tests | ❌ | ✅ | ✅ | ✅ |
| Disaster Recovery | ❌ | ❌ | ✅ | ✅ |
| Go-Live Review | ❌ | ❌ | ✅ | ✅ |
| Documentation | ⚠️ | ✅ | ✅ | ✅ |
| Production Ready | ❌ | ❌ | ⚠️ | ✅ |

---

## Version Numbering

### Semantic Versioning

ICYQuant follows semantic versioning (SemVer):

```
MAJOR.MINOR.PATCH-prerelease

Examples:
  0.4.0-alpha1    # Alpha prerelease of 0.4.0
  0.4.0-beta1     # Beta prerelease of 0.4.0
  0.4.0-rc1       # Release candidate 1 of 0.4.0
  0.4.0           # GA release of 0.4.0
  0.4.1           # Patch release
  0.5.0           # Minor release
  1.0.0           # Major release
```

### Version String Convention

| Component | Format | Example |
|-----------|--------|---------|
| Full version | `v{MAJOR}.{MINOR}.{PATCH}-{prerelease}` | v0.4.0-alpha1 |
| SDK version | `{MAJOR}.{MINOR}.{PATCH}` | 0.4.0 |
| Docker tag | `v{MAJOR}.{MINOR}.{PATCH}-{prerelease}` | v0.4.0-alpha1 |
| Helm version | `{MAJOR}.{MINOR}.{PATCH}` | 0.4.0 |
| Build ID | `build-{YYYYMMDD}-{stage}` | build-20260730-ga |

---

**Document Version**: 1.0
**Created**: 2026-07-30
**Last Updated**: 2026-07-30
**Status**: Effective
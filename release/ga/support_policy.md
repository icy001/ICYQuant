# ICYQuant v0.4.0-alpha1 Support Policy

## Overview

This document defines the support policy for ICYQuant v0.4.0-alpha1 GA. It outlines the different support phases, their duration, and the level of service provided during each phase.

---

## Support Phases

### Support Lifecycle Overview

```
| Release | Active Support | Maintenance Support | EOL |
|---------|---------------|---------------------|-----|
| v0.4.0-alpha1 GA | +3 months | +6 months | +9 months |
| (Released 2026-07-30) | Until 2026-10-30 | Until 2027-01-30 | After 2027-01-30 |
```

---

### Active Support (3 Months)

**Period**: From release date (2026-07-30) to 3 months after (2026-10-30)

During the Active Support phase, the following services are provided:

| Service | Description | Response Time |
|---------|-------------|---------------|
| **Security Updates** | Patches for security vulnerabilities | Within 4 hours (critical), 24 hours (high) |
| **Bug Fixes** | Fixes for all reported bugs | Within 2 business days (P0), 5 business days (P1) |
| **Performance Fixes** | Performance-related improvements | Next release cycle |
| **Compatibility Updates** | New platform/version support | As needed |
| **Documentation** | Documentation updates | Within 1 week of change |
| **Technical Support** | Direct technical assistance | Within 24 hours |

**Eligibility**: All users of v0.4.0-alpha1 GA

### Maintenance Support (6 Months)

**Period**: After Active Support ends to 6 months after release (2026-10-30 to 2027-01-30)

During the Maintenance Support phase, the following services are provided:

| Service | Description | Response Time |
|---------|-------------|---------------|
| **Security Updates** | Critical and high severity patches | Within 4 hours (critical), 48 hours (high) |
| **Bug Fixes** | Fixes for P0 and P1 bugs only | Within 5 business days |
| **Documentation** | Security-related documentation updates | Within 2 weeks |
| **Technical Support** | Best-effort technical assistance | Within 72 hours |

**Not Included**:
- New feature development
- P2/P3 bug fixes
- Performance improvements
- Platform compatibility updates

**Eligibility**: All users of v0.4.0-alpha1 GA

### End of Life (EOL)

**Period**: After Maintenance Support ends (after 2027-01-30)

After EOL, the following applies:

| Service | Status |
|---------|--------|
| Security Updates | ❌ No longer provided |
| Bug Fixes | ❌ No longer provided |
| Technical Support | ❌ No longer provided |
| Documentation | ⚠️ Archived only, no updates |
| Downloads | ❌ Removed from public repositories |

**Users are strongly encouraged to upgrade to a supported version before EOL.**

---

## LTS Designation

### What is LTS?

LTS (Long-Term Support) releases are designated for extended maintenance and stability. LTS releases receive 18 months of support (6 months active + 12 months maintenance) and are ideal for production environments requiring long-term stability.

### LTS Eligibility

A release may be designated as LTS if it meets the following criteria:

| Criteria | Description |
|----------|-------------|
| **Quality Gates** | All quality gates passed (unit test, integration, security, performance) |
| **Production Validation** | Successfully deployed and validated in at least 3 production environments |
| **Bug Free** | No P0 or P1 open issues for 30 consecutive days |
| **Feature Complete** | All planned features for the release are complete and stable |
| **Community Feedback** | Positive user feedback with no major issues reported |

### v0.4.0-alpha1 LTS Status

| Criteria | Status | Notes |
|----------|--------|-------|
| Quality Gates | ✅ Passed | All gates passed on 2026-07-30 |
| Production Validation | ✅ Passed | Validated in staging and pre-production |
| Bug Free | ✅ Passed | No P0/P1 open issues |
| Feature Complete | ✅ Passed | All v0.4.0 features complete |
| Community Feedback | ✅ Passed | Positive feedback during alpha cycle |

**LTS Designation**: v0.4.0-alpha1 GA is designated as an **LTS release**.

**Extended Support**: As an LTS release, v0.4.0-alpha1 receives:
- 6 months of Active Support (until 2027-01-30)
- 12 months of Maintenance Support (until 2028-01-30)
- Total support period: 18 months

### LTS Release Schedule

| Version | Release Date | LTS Status | Support End |
|---------|-------------|-----------|-------------|
| v0.4.0-alpha1 | 2026-07-30 | ✅ LTS | 2028-01-30 |
| v0.5.0 (planned) | TBD | Pending | TBD |

---

## Security Update Policy

### Vulnerability Severity Classification

| Severity | CVSS Score | Description |
|----------|-----------|-------------|
| **Critical** | 9.0 - 10.0 | Remote code execution, complete system compromise |
| **High** | 7.0 - 8.9 | Privilege escalation, data exposure |
| **Medium** | 4.0 - 6.9 | Limited data exposure, denial of service |
| **Low** | 0.1 - 3.9 | Minimal impact, unlikely to be exploited |
| **None** | 0.0 | No security impact |

### Security Update SLA

| Severity | Active Support | Maintenance Support |
|----------|---------------|-------------------|
| **Critical** | Patch within 4 hours, advisory within 2 hours | Patch within 4 hours, advisory within 2 hours |
| **High** | Patch within 24 hours, advisory within 8 hours | Patch within 48 hours, advisory within 24 hours |
| **Medium** | Patch within 72 hours, advisory within 48 hours | Advisory within 72 hours, patch next cycle |
| **Low** | Patch in next release cycle | Advisory only, no patch |

### Security Advisory Process

1. **Discovery**: Vulnerabilities discovered internally or reported by external researchers
2. **Triage**: Security team evaluates severity and impact within 1 hour
3. **Fix Development**: Patches developed and tested
4. **Pre-Announcement**: For critical/high, pre-notification to Enterprise customers
5. **Release**: Patch released with full advisory
6. **Public Disclosure**: Advisory published to [security.icyquant.io](https://security.icyquant.io)
7. **Tracking**: Vulnerability tracked until confirmed resolved

### Security Researcher Program

ICYQuant welcomes security researchers. For responsible disclosure:

- **Email**: security@icyquant.io
- **Policy**: See [security.icyquant.io/disclosure](https://security.icyquant.io/disclosure)
- **Recognition**: Researchers acknowledged in security advisories

---

## Upgrade Policy

### Recommended Upgrade Path

Users on v0.4.0-alpha1 GA should follow this upgrade path:

```
v0.4.0-alpha1 (GA) → v0.4.x (latest patch) → v0.5.0 (when available)
```

### Upgrade Recommendations

| Scenario | Recommendation |
|----------|---------------|
| **Production use** | Stay on LTS (v0.4.0-alpha1) or latest stable |
| **Development/Testing** | Upgrade to latest v0.4.x for bug fixes |
| **New deployments** | Use latest LTS or stable release |
| **Enterprise** | Follow enterprise upgrade schedule |

### Upgrade Notification

Users are notified of available upgrades through:

1. **In-product notifications**: Upgrade prompts in the dashboard
2. **Release notes**: Version-specific upgrade instructions
3. **Email notifications**: Subscription-based release announcements
4. **RSS feed**: Release RSS at [changelog.icyquant.io](https://changelog.icyquant.io)

### Upgrade Assistance

| Service | Availability | Description |
|---------|-------------|-------------|
| **Migration Guide** | Always | Documentation for version migration |
| **Migration Tool** | Always | `icyquant migrate` CLI tool |
| **Manual Assistance** | Enterprise tier | One-on-one migration support |
| **Rollback Support** | Always | Documented rollback procedures |

### Compatibility Commitment

ICYQuant commits to the following backward compatibility guarantees:

| Change Type | Guarantee |
|------------|-----------|
| **Patch versions** (0.4.0 → 0.4.1) | Fully backward compatible, zero breaking changes |
| **Minor versions** (0.4.x → 0.5.x) | Deprecated features with minimum 2 versions notice |
| **Major versions** (0.x → 1.x) | Breaking changes with 6 months advance notice |
| **API endpoints** | Deprecated endpoints maintained for 2 minor versions |
| **Database schema** | Forward and backward compatible within minor versions |

---

## Support Channels

### Community Support (Free)

| Channel | Availability | Response Time |
|---------|-------------|---------------|
| **GitHub Issues** | 24/7 | Within 48 hours |
| **Discord Community** | 24/7 | Community-driven, variable |
| **Documentation** | 24/7 | Self-service |
| **Knowledge Base** | 24/7 | Self-service |

### Professional Support (Paid)

| Tier | Availability | Response Time | SLA |
|------|-------------|---------------|-----|
| **Standard** | Business hours | Within 4 business hours | 99.5% uptime SLA |
| **Premium** | 24/7 | Within 1 hour (critical) | 99.9% uptime SLA |
| **Enterprise** | 24/7 dedicated | Within 15 minutes (critical) | 99.99% uptime SLA |

### Contact Information

| Channel | Contact |
|---------|---------|
| **Support Portal** | [support.icyquant.io](https://support.icyquant.io) |
| **Email** | support@icyquant.io |
| **Security** | security@icyquant.io |
| **Community** | [discord.gg/icyquant](https://discord.gg/icyquant) |

---

## Policy Changes

This support policy may be updated from time to time. Material changes will be:

1. Announced via release notes
2. Published on the policy page
3. Effective 30 days after announcement

| Version | Effective Date | Changes |
|---------|---------------|---------|
| 1.0 | 2026-07-30 | Initial policy for v0.4.0-alpha1 GA |

---

**Document Version**: 1.0
**Created**: 2026-07-30
**Last Updated**: 2026-07-30
**Status**: Effective
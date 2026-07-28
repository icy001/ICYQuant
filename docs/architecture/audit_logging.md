# Audit Logging Service

## Responsibility

Audit Service provides:

- User activity tracking
- Trading audit trail
- Risk decision history
- Compliance evidence

## Flow

Service Action

  |
  v
Audit Event

  |
  v
Audit Service

  |
  v
Immutable Storage

## Future Upgrade

Production Features:

- Event Sourcing Storage
- Hash Chain Verification
- Database WORM Storage
- Compliance Export
- SIEM Integration
- Long Term Archive
"""Risk authorization domain.

Owns the boundary between the risk engine's verdict and the order request
engine::

    Risk Decision
        -> Execution Authorization
        -> Authorization Certificate
        -> Scope Validation
        -> Execution Eligibility
        -> Order Request

A certificate is the formal authorization evidence the order request engine
consumes; it fixes the authorization scope, the approved quantity ceiling and
the TTL window, and is immutable.
"""

from services.risk.authorization.audit import (
    AuthorizationAuditRecord,
    AuthorizationAuditRepository,
    AuthorizationAuditTrail,
    InMemoryAuthorizationAuditRepository,
    audit_record_from_event,
    new_audit_id,
)
from services.risk.authorization.certificate import (
    AuthorizationCertificateIssuer,
    CertificateVerifier,
    ExecutionAuthorizationCertificate,
    certificate_expired,
    new_certificate_id,
    validate_certificate,
    verify_binding,
)
from services.risk.authorization.contract import (
    ExecutionAuthorization,
    RiskAuthorizationRequest,
    authorization_from_decision,
    new_authorization_id,
    new_request_id,
)
from services.risk.authorization.decision import (
    RiskDecision,
    approved_decision,
    new_decision_id,
    rejected_decision,
)
from services.risk.authorization.errors import (
    AuthorizationError,
    AuthorizationErrorCode,
    map_violation,
)
from services.risk.authorization.events import (
    AuthorizationEvent,
    AuthorizationEventFactory,
    AuthorizationEventMetadata,
    AuthorizationEventType,
    new_event_id,
)
from services.risk.authorization.integration import (
    AuthorizedExecutionContext,
    AuthorizationIntegrationService,
    AuthorizationResult,
)
from services.risk.authorization.scope import (
    AuthorizationScope,
    scope_from_certificate,
    scope_from_decision,
)
from services.risk.authorization.validator import (
    AuthorizationConsumption,
    AuthorizationConsumer,
    AuthorizationViolation,
    ExecutionEligibilityResult,
    ExecutionEligibilityValidator,
    ExecutionRequest,
)

__all__ = [
    "AuthorizedExecutionContext",
    "AuthorizationAuditRecord",
    "AuthorizationAuditRepository",
    "AuthorizationAuditTrail",
    "AuthorizationCertificateIssuer",
    "AuthorizationConsumption",
    "AuthorizationConsumer",
    "AuthorizationError",
    "AuthorizationErrorCode",
    "AuthorizationEvent",
    "AuthorizationEventFactory",
    "AuthorizationEventMetadata",
    "AuthorizationEventType",
    "AuthorizationIntegrationService",
    "AuthorizationResult",
    "AuthorizationScope",
    "AuthorizationViolation",
    "CertificateVerifier",
    "ExecutionAuthorization",
    "ExecutionAuthorizationCertificate",
    "ExecutionEligibilityResult",
    "ExecutionEligibilityValidator",
    "ExecutionRequest",
    "InMemoryAuthorizationAuditRepository",
    "RiskAuthorizationRequest",
    "RiskDecision",
    "approved_decision",
    "audit_record_from_event",
    "authorization_from_decision",
    "certificate_expired",
    "map_violation",
    "new_audit_id",
    "new_authorization_id",
    "new_certificate_id",
    "new_decision_id",
    "new_event_id",
    "new_request_id",
    "rejected_decision",
    "scope_from_certificate",
    "scope_from_decision",
    "validate_certificate",
    "verify_binding",
]

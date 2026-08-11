"""Cross-Domain Control Contract definitions.

Commit 21 Part 1.2 — Unified communication contract for all institutional control domains.
"""

from .contract_errors import (
    ContractError,
    ContractValidationError,
    ContractVersionError,
    ContractExpiredError,
    ContractReplayError,
    ContextIntegrityError,
    ConstraintConflictError,
)
from .control_version import (
    ContractVersion,
    VersionCompatibility,
    check_compatibility,
)
from .control_reason import (
    ReasonCode,
    REASON_CODE_LABELS,
)
from .control_context import ContractControlContext
from .control_request import (
    ControlRequest,
    RiskRequest,
    GovernanceRequest,
    AuthorityRequest,
    ApprovalRequest,
)
from .control_response import (
    ControlResponseStatus,
    ControlResponse,
)
from .control_evidence import (
    ControlEvidence,
    RiskEvidence,
    GovernanceEvidence,
    AuthorityEvidence,
    ApprovalEvidence,
)
from .control_constraint import (
    ConstraintType,
    ConstraintSource,
    ConstraintRule,
    ControlConstraint,
    EffectiveConstraints,
    intersect_constraints,
)
from .control_reference import (
    ControlReference,
    DecisionLineage,
)
from .control_decision import (
    DecisionStatus,
    ControlDecision,
)
from .control_contract import (
    ControlContract,
)

__all__ = [
    # Errors
    "ContractError",
    "ContractValidationError",
    "ContractVersionError",
    "ContractExpiredError",
    "ContractReplayError",
    "ContextIntegrityError",
    "ConstraintConflictError",
    # Version
    "ContractVersion",
    "VersionCompatibility",
    "check_compatibility",
    # Reason
    "ReasonCode",
    "REASON_CODE_LABELS",
    # Context
    "ContractControlContext",
    # Request
    "ControlRequest",
    "RiskRequest",
    "GovernanceRequest",
    "AuthorityRequest",
    "ApprovalRequest",
    # Response
    "ControlResponseStatus",
    "ControlResponse",
    # Evidence
    "ControlEvidence",
    "RiskEvidence",
    "GovernanceEvidence",
    "AuthorityEvidence",
    "ApprovalEvidence",
    # Constraint
    "ConstraintType",
    "ConstraintSource",
    "ConstraintRule",
    "ControlConstraint",
    "EffectiveConstraints",
    "intersect_constraints",
    # Reference
    "ControlReference",
    "DecisionLineage",
    # Decision
    "DecisionStatus",
    "ControlDecision",
    # Contract
    "ControlContract",
]

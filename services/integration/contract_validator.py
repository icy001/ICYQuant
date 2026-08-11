"""Contract Validator — validates every cross-domain contract before execution.

Checks contract structure, required fields, context integrity,
version compatibility, timestamps, and expiry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts.control_contract import ControlContract
from .contracts.control_version import ContractVersion
from .contracts.contract_errors import (
    ContractError,
    ContractValidationError,
    ContractExpiredError,
    ContextIntegrityError,
)
from .contract_registry import ContractRegistry


# ── Validation result ──

@dataclass
class ValidationResult:
    """Result of a contract validation pass."""

    valid: bool = True
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)

    def add_error(self, field: str, message: str) -> None:
        self.valid = False
        self.errors.append({"field": field, "message": message})

    def add_warning(self, field: str, message: str) -> None:
        self.warnings.append({"field": field, "message": message})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def __repr__(self) -> str:
        return f"ValidationResult(valid={self.valid}, errors={len(self.errors)}, warnings={len(self.warnings)})"


# ── Contract Validator ──

@dataclass
class ContractValidator:
    """Validates cross-domain control contracts for structural and semantic correctness.

    Checks performed:
      1. contract_id is non-empty.
      2. contract_version is parseable.
      3. domain is one of the known domains.
      4. context has a valid flow_id.
      5. request is present and has a valid domain match.
      6. timestamps are in the past (no future timestamps).
      7. expiry has not passed.
      8. constraints have valid provenance.
      9. references form a valid chain (if present).
    """

    registry: Optional[ContractRegistry] = None

    KNOWN_DOMAINS: tuple = ("risk", "governance", "authority", "approval", "admission")

    def validate(self, contract: ControlContract) -> ValidationResult:
        """Run all validation checks and return a combined result."""
        result = ValidationResult()

        self._check_identity(contract, result)
        self._check_version(contract, result)
        self._check_domain(contract, result)
        self._check_context(contract, result)
        self._check_request(contract, result)
        self._check_timestamps(contract, result)
        self._check_expiry(contract, result)
        self._check_constraints(contract, result)
        self._check_references(contract, result)

        return result

    def _check_identity(self, contract: ControlContract, result: ValidationResult) -> None:
        if not contract.contract_id:
            result.add_error("contract_id", "contract_id must not be empty")

    def _check_version(self, contract: ControlContract, result: ValidationResult) -> None:
        if not contract.contract_version:
            result.add_error("contract_version", "contract_version must not be empty")
            return
        try:
            ContractVersion.parse(contract.contract_version)
        except (ValueError, TypeError):
            result.add_error("contract_version",
                             f"Invalid version format: '{contract.contract_version}'")

    def _check_domain(self, contract: ControlContract, result: ValidationResult) -> None:
        if not contract.domain:
            result.add_error("domain", "domain must not be empty")
            return
        if contract.domain not in self.KNOWN_DOMAINS:
            result.add_warning("domain",
                               f"Unknown domain '{contract.domain}'. "
                               f"Known: {', '.join(self.KNOWN_DOMAINS)}")

    def _check_context(self, contract: ControlContract, result: ValidationResult) -> None:
        ctx = contract.context
        if not ctx.flow_id:
            result.add_error("context.flow_id", "context flow_id must not be empty")

    def _check_request(self, contract: ControlContract, result: ValidationResult) -> None:
        req = contract.request
        if not req.request_id:
            result.add_error("request.request_id", "request_id must not be empty")
        if req.domain != contract.domain:
            result.add_error("request.domain",
                             f"Request domain '{req.domain}' != contract domain '{contract.domain}'")

    def _check_timestamps(self, contract: ControlContract, result: ValidationResult) -> None:
        now = time.time()
        if contract.created_at > now + 1.0:  # allow 1s clock skew
            result.add_error("created_at", "created_at is in the future")
        if contract.context.created_at > now + 1.0:
            result.add_error("context.created_at", "context created_at is in the future")

    def _check_expiry(self, contract: ControlContract, result: ValidationResult) -> None:
        if contract.is_expired:
            result.add_error("expires_at",
                             f"Contract expired at {contract.expires_at}")
        if contract.request.is_expired:
            result.add_error("request.ttl_seconds",
                             "Request has exceeded its TTL")

    def _check_constraints(self, contract: ControlContract, result: ValidationResult) -> None:
        for c in contract.constraints:
            if not c.source:
                result.add_warning("constraints.source",
                                   f"Constraint '{c.constraint_type.name}' has no source")
            if c.is_expired:
                result.add_warning("constraints.expires_at",
                                   f"Constraint '{c.constraint_type.name}' is expired")

    def _check_references(self, contract: ControlContract, result: ValidationResult) -> None:
        if not contract.references:
            return
        # Verify parent references exist within the list (all entries, not just index 1+)
        ids = {r.reference_id for r in contract.references}
        for r in contract.references:
            if r.parent_reference_id is not None and r.parent_reference_id not in ids:
                result.add_error("references",
                                 f"Reference '{r.reference_id}' has unknown parent "
                                 f"'{r.parent_reference_id}'")

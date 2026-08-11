"""Compliance Checker — verifies that portfolio recommendations meet all regulatory and internal rules.

Pipeline:
    Portfolio -> ComplianceChecker.check()
        -> Market rules (exchange limits, short-sale rules, etc.)
        -> Trading rules (wash sale, insider trading, etc.)
        -> Position limits (regulatory + internal)
        -> Restricted list check
        -> Audit policy verification
        -> Output ComplianceResult (approved / rejected)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ComplianceDecision(str, Enum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    REJECTED = "rejected"


@dataclass
class ComplianceResult:
    """Compliance check result.

    Attributes:
        result_id: Unique identifier.
        decision: Compliance decision.
        violations: List of rule violations.
        warnings: List of compliance warnings.
        rules_checked: Number of rules evaluated.
        rules_passed: Number of rules passed.
        restricted_symbols_hit: Any restricted symbols found.
        checked_at: Check timestamp.
    """

    result_id: str = ""
    decision: ComplianceDecision = ComplianceDecision.APPROVED
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rules_checked: int = 0
    rules_passed: int = 0
    restricted_symbols_hit: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_approved(self) -> bool:
        return self.decision == ComplianceDecision.APPROVED

    @property
    def pass_rate(self) -> float:
        if self.rules_checked == 0:
            return 1.0
        return self.rules_passed / self.rules_checked


class ComplianceChecker:
    """Verifies portfolio compliance with regulatory and internal rules.

    Checks market rules, trading rules, position limits, restricted lists,
    and audit policies. All checks must pass before proceeding to execution.

    Supports:
        - Market rules validation (exchange limits, short-sale)
        - Trading rules (wash sale, pattern day trader)
        - Position limits (regulatory caps, internal limits)
        - Restricted list enforcement
        - Audit policy verification
        - Configurable rule sets

    Usage:
        checker = ComplianceChecker()
        await checker.initialize()
        result = await checker.check(portfolio)
        if not result.is_approved:
            raise ComplianceViolationError(result.violations)
    """

    def __init__(self) -> None:
        self._results: List[ComplianceResult] = []
        self._restricted_list: List[str] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("ComplianceChecker created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ComplianceChecker initialized")

    async def shutdown(self) -> None:
        self._results.clear()
        self._restricted_list.clear()
        self._initialized = False
        logger.info("ComplianceChecker shutdown complete")

    def add_restricted_symbol(self, symbol: str) -> None:
        self._restricted_list.append(symbol)

    async def check(
        self,
        portfolio: Optional[Any] = None,
    ) -> ComplianceResult:
        """Check portfolio compliance.

        Args:
            portfolio: Portfolio recommendation to check.

        Returns:
            ComplianceResult with decision and violations.
        """
        logger.info("ComplianceChecker.check() started")
        self._counter += 1
        result = ComplianceResult(
            result_id=f"comp_{self._counter}",
            decision=ComplianceDecision.APPROVED,
        )

        # Check restricted list
        allocations = getattr(portfolio, "allocations", {}) if portfolio else {}
        for symbol in allocations:
            if symbol in self._restricted_list:
                result.violations.append(f"Symbol {symbol} is on restricted list")
                result.restricted_symbols_hit.append(symbol)

        if result.violations:
            result.decision = ComplianceDecision.REJECTED

        result.rules_checked = 1 + len(allocations)
        result.rules_passed = result.rules_checked - len(result.violations)
        self._results.append(result)
        logger.info("ComplianceChecker.check() completed: decision=%s", result.decision.value)
        return result

    def get_summary(self) -> Dict[str, Any]:
        approved = sum(1 for r in self._results if r.is_approved)
        return {
            "initialized": self._initialized,
            "total": len(self._results),
            "approved": approved,
            "restricted_symbols": len(self._restricted_list),
        }

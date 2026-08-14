"""
Risk decision service (Commit 41 Part 1.5) — application layer entry.

The application layer owns the stable entry point of the risk decision
pipeline:

    Context Builder
          |
          v
    Rule Engine
          |
          v
    Decision Builder
          |
          v
    Trace Builder
          |
          v
    Audit

``RiskDecisionService`` is re-exported here so the application layer and the
``services.risk.service`` orchestration module share a single class: the
implementation stays in one place and there is no behavioural drift between
import paths.
"""

from __future__ import annotations

from ..service.risk_decision_service import RiskDecisionService

__all__ = [
    "RiskDecisionService",
]

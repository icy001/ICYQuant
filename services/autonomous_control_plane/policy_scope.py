"""
Policy Scope — Hierarchical policy scope definitions.

Defines the scope taxonomy for policies and determines
which policies apply to a given decision.
"""

from __future__ import annotations

from enum import Enum


class PolicyScope(Enum):
    """Hierarchical policy scopes."""
    GLOBAL = "global"
    SYSTEM = "system"
    RESEARCH = "research"
    ALPHA = "alpha"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    EXECUTION = "execution"
    CAPITAL = "capital"
    PRODUCTION = "production"
    APPROVAL = "approval"
    LIFECYCLE = "lifecycle"


# Scope hierarchy — broader scopes apply to narrower ones
SCOPE_HIERARCHY: dict[PolicyScope, list[PolicyScope]] = {
    PolicyScope.GLOBAL: [
        PolicyScope.SYSTEM, PolicyScope.RESEARCH, PolicyScope.ALPHA,
        PolicyScope.STRATEGY, PolicyScope.PORTFOLIO, PolicyScope.RISK,
        PolicyScope.EXECUTION, PolicyScope.CAPITAL, PolicyScope.PRODUCTION,
        PolicyScope.APPROVAL, PolicyScope.LIFECYCLE,
    ],
    PolicyScope.SYSTEM: [
        PolicyScope.RESEARCH, PolicyScope.ALPHA, PolicyScope.STRATEGY,
        PolicyScope.EXECUTION, PolicyScope.CAPITAL, PolicyScope.PRODUCTION,
    ],
    PolicyScope.RESEARCH: [PolicyScope.ALPHA],
    PolicyScope.ALPHA: [PolicyScope.STRATEGY],
    PolicyScope.STRATEGY: [PolicyScope.PORTFOLIO],
    PolicyScope.PORTFOLIO: [PolicyScope.RISK, PolicyScope.EXECUTION],
    PolicyScope.RISK: [PolicyScope.EXECUTION, PolicyScope.CAPITAL],
    PolicyScope.CAPITAL: [],
    PolicyScope.PRODUCTION: [],
    PolicyScope.APPROVAL: [],
    PolicyScope.LIFECYCLE: [],
}


def get_applicable_scopes(requested_scope: str) -> list[str]:
    """Get all scopes that apply to a given requested scope."""
    try:
        scope = PolicyScope(requested_scope)
    except ValueError:
        return [requested_scope]

    applicable = [scope.value]

    # Add broader scopes that cover this scope
    for broader, narrower in SCOPE_HIERARCHY.items():
        if scope in narrower:
            applicable.append(broader.value)

    # Always add global
    if PolicyScope.GLOBAL.value not in applicable:
        applicable.append(PolicyScope.GLOBAL.value)

    return applicable


def is_scope_covered(requested: str, policy_scope: str) -> bool:
    """Check whether a policy scope covers a requested scope."""
    if policy_scope == PolicyScope.GLOBAL.value:
        return True
    if policy_scope == requested:
        return True
    try:
        p_scope = PolicyScope(policy_scope)
        r_scope = PolicyScope(requested)
        return r_scope in SCOPE_HIERARCHY.get(p_scope, [])
    except ValueError:
        return policy_scope == requested

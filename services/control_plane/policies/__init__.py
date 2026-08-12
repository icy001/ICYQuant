"""
Concrete operational policies.

Each module exposes a ``build_*_policy()`` factory returning a versioned
:class:`~services.control_plane.policy.Policy` plus the policy constants
(``POLICY_ID`` / ``POLICY_VERSION``) for auditing.
"""

from .emergency_policy import build_emergency_policy
from .health_policy import build_health_policy
from .recovery_policy import build_recovery_policy
from .risk_policy import build_risk_policy
from .trading_policy import build_trading_policy

#: Factory functions for every built-in policy, in registration order.
DEFAULT_POLICY_BUILDERS = (
    build_emergency_policy,
    build_risk_policy,
    build_health_policy,
    build_recovery_policy,
    build_trading_policy,
)


def build_default_policies():
    """Build every built-in policy as a list (deterministic order)."""
    return [builder() for builder in DEFAULT_POLICY_BUILDERS]


__all__ = [
    "build_trading_policy",
    "build_health_policy",
    "build_recovery_policy",
    "build_risk_policy",
    "build_emergency_policy",
    "build_default_policies",
    "DEFAULT_POLICY_BUILDERS",
]

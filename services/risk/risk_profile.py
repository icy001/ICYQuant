"""
Risk Profile — Account-level risk profile management.

Defines risk profiles at Account, Portfolio, and Strategy levels
with configurable risk levels and constraints.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk tolerance levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class ProfileScope(str, Enum):
    """Risk profile scope."""
    ACCOUNT = "account"
    PORTFOLIO = "portfolio"
    STRATEGY = "strategy"
    INSTRUMENT = "instrument"


@dataclass
class RiskProfile:
    """Account/portfolio/strategy risk profile."""
    profile_id: str
    scope: ProfileScope = ProfileScope.ACCOUNT
    risk_level: RiskLevel = RiskLevel.MODERATE
    name: str = ""
    description: str = ""

    # Limits
    max_position_pct: float = 20.0
    max_drawdown_pct: float = 25.0
    max_leverage: float = 2.0
    max_exposure_pct: float = 100.0
    daily_loss_limit: float = 0.0
    var_limit: float = 0.0
    cvar_limit: float = 0.0

    # Constraints
    concentration_limit_pct: float = 10.0
    min_liquidity_score: float = 0.0
    max_correlation: float = 0.85

    # Policy associations
    policy_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RiskProfileManager:
    """
    Manages risk profiles for accounts, portfolios, and strategies.

    Different accounts can adopt different risk profiles with
    customized limits and constraints.

    Usage::

        mgr = RiskProfileManager()
        await mgr.initialize()
        profile = await mgr.create(RiskProfile(
            profile_id="account_001_profile",
            scope=ProfileScope.ACCOUNT,
            risk_level=RiskLevel.CONSERVATIVE,
            max_leverage=1.0,
        ))
    """

    def __init__(self) -> None:
        self._profiles: dict[str, RiskProfile] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the profile manager."""
        logger.info("RiskProfileManager initialized.")

    async def stop(self) -> None:
        """Stop the profile manager."""
        logger.info("RiskProfileManager stopped.")

    # ---- CRUD ----

    async def create(self, profile: RiskProfile) -> RiskProfile:
        """Create a risk profile."""
        async with self._lock:
            self._profiles[profile.profile_id] = profile
        logger.info(f"Risk profile created: {profile.profile_id} ({profile.scope.value})")
        return profile

    async def update(self, profile_id: str, **kwargs: Any) -> Optional[RiskProfile]:
        """Update a risk profile."""
        async with self._lock:
            profile = self._profiles.get(profile_id)
            if not profile:
                return None
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            profile.updated_at = datetime.now(timezone.utc)
        return profile

    async def delete(self, profile_id: str) -> bool:
        """Delete a risk profile."""
        async with self._lock:
            if profile_id in self._profiles:
                del self._profiles[profile_id]
                return True
            return False

    async def get(self, profile_id: str) -> Optional[RiskProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)

    async def list_by_scope(self, scope: ProfileScope) -> list[RiskProfile]:
        """List profiles by scope."""
        return [p for p in self._profiles.values() if p.scope == scope]

    async def list_by_risk_level(self, level: RiskLevel) -> list[RiskProfile]:
        """List profiles by risk level."""
        return [p for p in self._profiles.values() if p.risk_level == level]

    async def list_all(self) -> list[RiskProfile]:
        """List all profiles."""
        return list(self._profiles.values())

    # ---- Policy Association ----

    async def add_policy(self, profile_id: str, policy_id: str) -> bool:
        """Associate a policy with a profile."""
        profile = self._profiles.get(profile_id)
        if not profile or policy_id in profile.policy_ids:
            return False
        profile.policy_ids.append(policy_id)
        profile.updated_at = datetime.now(timezone.utc)
        return True

    async def remove_policy(self, profile_id: str, policy_id: str) -> bool:
        """Remove a policy association."""
        profile = self._profiles.get(profile_id)
        if not profile or policy_id not in profile.policy_ids:
            return False
        profile.policy_ids.remove(policy_id)
        profile.updated_at = datetime.now(timezone.utc)
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check profile manager health."""
        return {
            "status": "healthy",
            "total_profiles": len(self._profiles),
        }

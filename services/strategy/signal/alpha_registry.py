"""
Alpha Registry — Alpha model registration and discovery.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Alpha model type registration
    - Multi-version alpha support
    - Capability-based discovery
    - Active/inactive tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.alpha_engine import AlphaType, AlphaStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class AlphaInfo:
    """Metadata for a registered alpha model."""
    alpha_id: str
    name: str = ""
    alpha_type: AlphaType = AlphaType.CUSTOM
    version: str = "1.0"
    description: str = ""
    author: str = ""
    status: AlphaStatus = AlphaStatus.ACTIVE

    # Capabilities
    supported_instruments: List[str] = field(default_factory=list)
    requires_factors: List[str] = field(default_factory=list)

    # Performance
    avg_ic: float = 0.0
    avg_ir: float = 0.0
    half_life_days: float = 30.0

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Alpha Registry
# ---------------------------------------------------------------------------

class AlphaRegistry:
    """Central registry for alpha models."""

    def __init__(self):
        self._alphas: Dict[str, Dict[str, AlphaInfo]] = {}  # alpha_id → version → info
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._register_builtin_alphas()
        self._initialized = True
        logger.info("AlphaRegistry initialized with %d alphas", len(self._alphas))

    async def shutdown(self) -> None:
        self._alphas.clear()
        self._initialized = False

    def _register_builtin_alphas(self) -> None:
        """Register default alpha model types."""
        builtins = [
            AlphaInfo(
                alpha_id="momentum_alpha",
                name="Momentum Alpha",
                alpha_type=AlphaType.RULE,
                description="Cross-sectional momentum alpha",
                requires_factors=["momentum_1m", "momentum_3m", "momentum_6m"],
            ),
            AlphaInfo(
                alpha_id="value_alpha",
                name="Value Alpha",
                alpha_type=AlphaType.RULE,
                description="Value factor alpha (PE, PB, etc.)",
                requires_factors=["pe_ratio", "pb_ratio", "dividend_yield"],
            ),
            AlphaInfo(
                alpha_id="quality_alpha",
                name="Quality Alpha",
                alpha_type=AlphaType.RULE,
                description="Quality factor alpha (ROE, margin, etc.)",
                requires_factors=["roe", "profit_margin", "debt_ratio"],
            ),
            AlphaInfo(
                alpha_id="volatility_alpha",
                name="Volatility Alpha",
                alpha_type=AlphaType.STATISTICAL,
                description="Volatility-based alpha",
                requires_factors=["realized_vol", "implied_vol", "beta"],
            ),
        ]
        for alpha in builtins:
            self._alphas.setdefault(alpha.alpha_id, {})[alpha.version] = alpha

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(self, info: AlphaInfo) -> None:
        """Register or update an alpha model."""
        if info.alpha_id not in self._alphas:
            self._alphas[info.alpha_id] = {}
        self._alphas[info.alpha_id][info.version] = info
        info.updated_at = datetime.now(timezone.utc)
        logger.info("Registered alpha: %s v%s", info.alpha_id, info.version)

    def get_alpha(self, alpha_id: str, version: str = "1.0") -> Optional[AlphaInfo]:
        versions = self._alphas.get(alpha_id, {})
        return versions.get(version)

    def get_latest(self, alpha_id: str) -> Optional[AlphaInfo]:
        versions = self._alphas.get(alpha_id, {})
        if not versions:
            return None
        # Sort by version string
        sorted_versions = sorted(versions.values(), key=lambda v: v.version)
        return sorted_versions[-1]

    def list_all(self) -> List[AlphaInfo]:
        result = []
        for versions in self._alphas.values():
            result.extend(versions.values())
        return result

    def list_active(self) -> List[AlphaInfo]:
        return [a for a in self.list_all() if a.status == AlphaStatus.ACTIVE]

    def list_by_type(self, alpha_type: AlphaType) -> List[AlphaInfo]:
        return [a for a in self.list_all() if a.alpha_type == alpha_type]

    def find_by_factor(self, factor_name: str) -> List[AlphaInfo]:
        return [a for a in self.list_all() if factor_name in a.requires_factors]

    def find_by_instrument(self, instrument: str) -> List[AlphaInfo]:
        return [a for a in self.list_all()
                if not a.supported_instruments or instrument in a.supported_instruments]

    def set_status(self, alpha_id: str, status: AlphaStatus, version: str = "1.0") -> bool:
        info = self.get_alpha(alpha_id, version)
        if info:
            info.status = status
            info.updated_at = datetime.now(timezone.utc)
            return True
        return False

    def unregister(self, alpha_id: str, version: Optional[str] = None) -> int:
        """Remove alpha(s). If version is None, removes all versions."""
        if alpha_id not in self._alphas:
            return 0
        if version:
            removed = 1 if self._alphas[alpha_id].pop(version, None) else 0
            if not self._alphas[alpha_id]:
                del self._alphas[alpha_id]
            return removed
        count = len(self._alphas[alpha_id])
        del self._alphas[alpha_id]
        return count

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def alpha_count(self) -> int:
        return sum(len(v) for v in self._alphas.values())

    @property
    def active_count(self) -> int:
        return len(self.list_active())

"""
Rollout package for feature flag percentage deployment.

Provides a complete percentage-based rollout system
with consistent hashing, sticky assignment, progressive
deployment, segment-based targeting, and scheduling.

Public API:
    - RolloutEngine: Unified evaluation entry point
    - RolloutPolicy: Rollout policy configuration
    - RolloutAssignment: Decision result
    - ConsistentHasher: Stable hash computation
    - StickyAssignment: Cached assignment engine
    - ProgressiveRollout: Multi-stage deployment
    - SegmentDefinition: Segment-based targeting
    - SegmentEngine: Segment matching
    - RolloutStrategy: Combined strategy
    - RolloutScheduler: Timed advancement
    - RolloutValidator: Configuration validation
    - RolloutMetrics: Prometheus metrics
    - RolloutAudit: Audit logging
    - RolloutCache: Dual-layer caching
"""

from __future__ import annotations

from .assignment import StickyAssignment
from .audit import RolloutAudit
from .cache import RolloutCache
from .engine import RolloutEngine
from .hasher import ConsistentHasher, compute_hash, is_in_percentage_rollout
from .metrics import RolloutMetrics
from .progressive import ProgressiveRollout, ProgressiveStage
from .rollout import (
    RolloutAssignment,
    RolloutPolicy,
    SegmentDefinition,
)
from .scheduler import (
    FREQUENCY_DAILY,
    FREQUENCY_IMMEDIATE,
    FREQUENCY_WEEKLY,
    RolloutScheduler,
    ScheduleConfig,
)
from .segment import SegmentEngine
from .strategy import RolloutStrategy
from .validator import RolloutValidator

__all__ = [
    # Engine
    "RolloutEngine",
    # Models
    "RolloutPolicy",
    "RolloutAssignment",
    "ProgressiveStage",
    "SegmentDefinition",
    # Core
    "ConsistentHasher",
    "StickyAssignment",
    "ProgressiveRollout",
    "SegmentEngine",
    "RolloutStrategy",
    "RolloutScheduler",
    "ScheduleConfig",
    "RolloutValidator",
    "RolloutMetrics",
    "RolloutAudit",
    "RolloutCache",
    # Utilities
    "compute_hash",
    "is_in_percentage_rollout",
    # Constants
    "FREQUENCY_IMMEDIATE",
    "FREQUENCY_DAILY",
    "FREQUENCY_WEEKLY",
]

"""
ICYQuant Cloud Native Runtime - Release Manager

Manages software release lifecycle with support for:
- Canary releases with automatic promotion
- Blue/Green deployments
- Rolling updates
- Automated rollback
- Release versioning
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ReleaseStatus(str, Enum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    DEPLOYING = "DEPLOYING"
    VERIFYING = "VERIFYING"
    PROMOTING = "PROMOTING"
    ROLLING_BACK = "ROLLING_BACK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReleaseStrategy(str, Enum):
    CANARY = "CANARY"
    BLUE_GREEN = "BLUE_GREEN"
    ROLLING = "ROLLING"
    RECREATE = "RECREATE"


class CanaryStage(str, Enum):
    STAGE_1 = 5      # 5% traffic
    STAGE_2 = 20     # 20% traffic
    STAGE_3 = 50     # 50% traffic
    STAGE_4 = 100    # Full rollout


@dataclass
class ReleaseQuality:
    error_rate: float = 0.0
    p95_latency_ms: float = 0.0
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    orders_processed: int = 0
    risk_events: int = 0
    passed: bool = True
    message: str = ""

    def to_dict(self) -> Dict:
        return {
            "errorRate": self.error_rate,
            "p95LatencyMs": self.p95_latency_ms,
            "cpuUtilization": self.cpu_utilization,
            "memoryUtilization": self.memory_utilization,
            "ordersProcessed": self.orders_processed,
            "riskEvents": self.risk_events,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass
class Release:
    id: str
    version: str
    service: str
    image: str
    strategy: ReleaseStrategy
    status: ReleaseStatus = ReleaseStatus.CREATED
    stages: List[int] = field(default_factory=lambda: [5, 20, 50, 100])
    current_stage: int = 0
    canary_weight: int = 0
    quality_metrics: Optional[ReleaseQuality] = None
    auto_promote: bool = True
    promoted_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    error_message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "version": self.version,
            "service": self.service,
            "image": self.image,
            "strategy": self.strategy.value,
            "status": self.status.value,
            "currentStage": self.current_stage,
            "canaryWeight": self.canary_weight,
            "quality": self.quality_metrics.to_dict() if self.quality_metrics else None,
            "autoPromote": self.auto_promote,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "errorMessage": self.error_message,
        }


class ReleaseManager:
    """
    Release management for ICYQuant platform.

    Provides:
    - Structured release lifecycle
    - Canary releases with staged promotion
    - Quality gate evaluation
    - Automatic rollback on failure
    - Release history tracking
    """

    def __init__(self):
        self._releases: Dict[str, Release] = {}
        self._release_history: List[Release] = []
        self._quality_gates: Dict[str, ReleaseQuality] = {}
        self._event_handlers: Dict[str, List] = {
            "release_started": [],
            "release_completed": [],
            "release_failed": [],
            "release_rolled_back": [],
            "stage_promoted": [],
        }

    def create_release(
        self,
        version: str,
        service: str,
        image: str,
        strategy: ReleaseStrategy = ReleaseStrategy.CANARY,
        stages: Optional[List[int]] = None,
        auto_promote: bool = True,
    ) -> Release:
        release_id = str(uuid.uuid4())[:12]
        release = Release(
            id=release_id,
            version=version,
            service=service,
            image=image,
            strategy=strategy,
            status=ReleaseStatus.PREPARING,
            stages=stages or [5, 20, 50, 100],
            auto_promote=auto_promote,
        )
        self._releases[release_id] = release
        self._fire_event("release_started", release)
        return release

    def start_release(self, release_id: str) -> Optional[Release]:
        release = self._releases.get(release_id)
        if not release:
            return None
        release.status = ReleaseStatus.DEPLOYING
        release.canary_weight = release.stages[0] if release.stages else 100
        release.updated_at = datetime.now()
        return release

    def promote_stage(
        self,
        release_id: str,
        quality_metrics: Optional[ReleaseQuality] = None,
    ) -> Optional[Release]:
        release = self._releases.get(release_id)
        if not release:
            return None

        if quality_metrics:
            release.quality_metrics = quality_metrics
            if not quality_metrics.passed:
                return self.rollback_release(release_id)

        if release.current_stage < len(release.stages) - 1:
            release.current_stage += 1
            release.canary_weight = release.stages[release.current_stage]
            release.status = ReleaseStatus.PROMOTING
            release.updated_at = datetime.now()
            self._fire_event("stage_promoted", release)

            if release.canary_weight >= 100:
                release.status = ReleaseStatus.COMPLETED
                release.completed_at = datetime.now()
                release.promoted_at = datetime.now()
                self._archive_release(release)
                self._fire_event("release_completed", release)
        else:
            release.status = ReleaseStatus.COMPLETED
            release.completed_at = datetime.now()
            self._archive_release(release)
            self._fire_event("release_completed", release)

        return release

    def complete_release(self, release_id: str) -> Optional[Release]:
        release = self._releases.get(release_id)
        if not release:
            return None
        release.status = ReleaseStatus.COMPLETED
        release.completed_at = datetime.now()
        self._archive_release(release)
        self._fire_event("release_completed", release)
        return release

    def rollback_release(
        self,
        release_id: str,
        reason: str = "",
    ) -> Optional[Release]:
        release = self._releases.get(release_id)
        if not release:
            return None
        release.status = ReleaseStatus.ROLLING_BACK
        release.error_message = reason or "Rolled back due to quality gate failure"
        release.rolled_back_at = datetime.now()
        release.updated_at = datetime.now()
        self._fire_event("release_rolled_back", release)
        return release

    def cancel_release(self, release_id: str) -> Optional[Release]:
        release = self._releases.get(release_id)
        if not release:
            return None
        release.status = ReleaseStatus.CANCELLED
        release.updated_at = datetime.now()
        return release

    def get_release(self, release_id: str) -> Optional[Release]:
        return self._releases.get(release_id)

    def list_releases(
        self,
        service: Optional[str] = None,
        status: Optional[ReleaseStatus] = None,
    ) -> List[Release]:
        results = list(self._releases.values())
        if service:
            results = [r for r in results if r.service == service]
        if status:
            results = [r for r in results if r.status == status]
        return results

    def evaluate_quality_gate(
        self,
        release_id: str,
        metrics: ReleaseQuality,
        thresholds: Optional[Dict] = None,
    ) -> Release:
        release = self._releases.get(release_id)
        if not release:
            return None

        default_thresholds = {
            "error_rate": 1.0,
            "p95_latency_ms": 500,
            "cpu_utilization": 80,
            "memory_utilization": 85,
            "risk_events": 0,
        }
        thresholds = thresholds or default_thresholds

        passed = True
        reasons = []

        if metrics.error_rate > thresholds.get("error_rate", 1.0):
            passed = False
            reasons.append(f"Error rate {metrics.error_rate:.2f}% > {thresholds['error_rate']}%")

        if metrics.p95_latency_ms > thresholds.get("p95_latency_ms", 500):
            passed = False
            reasons.append(f"P95 latency {metrics.p95_latency_ms}ms > {thresholds['p95_latency_ms']}ms")

        if metrics.cpu_utilization > thresholds.get("cpu_utilization", 80):
            passed = False
            reasons.append(f"CPU utilization {metrics.cpu_utilization}% > {thresholds['cpu_utilization']}%")

        if metrics.risk_events > thresholds.get("risk_events", 0):
            passed = False
            reasons.append(f"Risk events: {metrics.risk_events}")

        metrics.passed = passed
        metrics.message = "; ".join(reasons) if reasons else "All checks passed"

        release.quality_metrics = metrics
        self._quality_gates[release_id] = metrics
        return release

    def on_event(self, event: str, handler):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def get_status(self) -> Dict:
        return {
            "activeReleases": len([
                r for r in self._releases.values()
                if r.status not in (ReleaseStatus.COMPLETED, ReleaseStatus.CANCELLED)
            ]),
            "releases": {r.id: r.to_dict() for r in self._releases.values()},
            "history": [r.to_dict() for r in self._release_history[-10:]],
            "qualityGates": {k: v.to_dict() for k, v in self._quality_gates.items()},
        }

    def _archive_release(self, release: Release):
        self._release_history.append(release)
        if len(self._release_history) > 500:
            self._release_history = self._release_history[-500:]

    def _fire_event(self, event: str, release: Release):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(release)
            except Exception as e:
                logger.error(f"Event handler error for {event}: {e}")
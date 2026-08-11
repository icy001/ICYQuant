"""Alpha Candidate — First-class alpha candidate object.

Each alpha is a tracked entity with full lifecycle:
DISCOVERED → TESTING → VALIDATED → CANDIDATE → REJECTED/PROMOTED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlphaCandidate:
    alpha_id: str
    factors: List[str] = field(default_factory=list)
    feature_versions: Dict[str, str] = field(default_factory=dict)
    factor_versions: Dict[str, str] = field(default_factory=dict)
    hypothesis_id: Optional[str] = None
    experiment_id: Optional[str] = None
    training_dataset: Optional[str] = None
    performance: Dict[str, Any] = field(default_factory=dict)
    risk_metrics: Dict[str, Any] = field(default_factory=dict)
    turnover: float = 0.0
    capacity: float = 0.0
    status: str = "discovered"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "factors": self.factors,
            "hypothesis_id": self.hypothesis_id,
            "status": self.status,
            "performance": self.performance,
            "risk_metrics": self.risk_metrics,
        }

"""Factor Context — shared context propagated through all factor operations.

Carries session, trace, user, workspace, and factor-specific configuration
across the factor research engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class FactorContext:
    """Contextual data propagated through factor research operations.

    Carries:
    * Session/trace identifiers
    * User/workspace identity
    * Universe and benchmark configuration
    * Data frequency and lookback settings
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    experiment_id: Optional[str] = None
    universe: List[str] = field(default_factory=list)
    benchmark: str = "CSI300"
    frequency: str = "daily"  # daily, weekly, monthly
    lookback_days: int = 252
    forward_days: int = 1
    config: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_overrides(self, **kwargs) -> "FactorContext":
        new_ctx = FactorContext(
            session_id=self.session_id,
            trace_id=kwargs.get("trace_id", self.trace_id),
            user_id=kwargs.get("user_id", self.user_id),
            workspace_id=kwargs.get("workspace_id", self.workspace_id),
            project_id=kwargs.get("project_id", self.project_id),
            experiment_id=kwargs.get("experiment_id", self.experiment_id),
            universe=kwargs.get("universe", self.universe),
            benchmark=kwargs.get("benchmark", self.benchmark),
            frequency=kwargs.get("frequency", self.frequency),
            lookback_days=kwargs.get("lookback_days", self.lookback_days),
            forward_days=kwargs.get("forward_days", self.forward_days),
            config={**self.config, **kwargs.get("config", {})},
            tags={**self.tags, **kwargs.get("tags", {})},
            metadata={**self.metadata, **kwargs.get("metadata", {})},
        )
        return new_ctx

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "universe": self.universe,
            "benchmark": self.benchmark,
            "frequency": self.frequency,
            "lookback_days": self.lookback_days,
            "forward_days": self.forward_days,
            "config": self.config,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"FactorContext(session={self.session_id[:8]})"

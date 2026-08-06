"""Research Context — shared contextual data for the research platform.

The :class:`ResearchContext` carries session-level state including
user identity, workspace, configuration, and tracing information
across all research platform operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class ResearchContext:
    """Shared context propagated through all research operations.

    Carries:
    * Session and trace identifiers
    * User/workspace identity
    * Global configuration overrides
    * Feature flags and environment metadata
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    manager_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    feature_flags: Dict[str, bool] = field(default_factory=dict)

    def with_overrides(self, **kwargs) -> "ResearchContext":
        """Create a new context with the given overrides applied."""
        new_ctx = ResearchContext(
            session_id=self.session_id,
            manager_id=self.manager_id,
            trace_id=self.trace_id,
            user_id=kwargs.get("user_id", self.user_id),
            workspace_id=kwargs.get("workspace_id", self.workspace_id),
            project_id=kwargs.get("project_id", self.project_id),
            config={**self.config, **kwargs.get("config", {})},
            tags={**self.tags, **kwargs.get("tags", {})},
            metadata={**self.metadata, **kwargs.get("metadata", {})},
            feature_flags={**self.feature_flags, **kwargs.get("feature_flags", {})},
        )
        return new_ctx

    def is_feature_enabled(self, flag: str) -> bool:
        """Check if a feature flag is enabled in this context."""
        return self.feature_flags.get(flag, False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "manager_id": self.manager_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "config": self.config,
            "tags": self.tags,
            "metadata": self.metadata,
            "feature_flags": self.feature_flags,
        }

    def __repr__(self) -> str:
        return f"ResearchContext(session={self.session_id[:8]})"


def create_research_context(
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    **kwargs,
) -> ResearchContext:
    """Factory for creating a ResearchContext with common defaults."""
    return ResearchContext(
        user_id=user_id,
        workspace_id=workspace_id,
        **kwargs,
    )

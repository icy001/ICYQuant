"""AI Session — Session management for AI interactions.

An AISession represents a single interaction context with the AI Platform.
It carries request parameters, authentication, parameters, and state
throughout the AI processing lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_platform import AIPlatformMode


@dataclass
class AISession:
    """AI Session — encapsulates a single AI interaction.

    Each session represents one complete interaction cycle:
    - A request enters the platform
    - AI subsystems process it
    - A result (prediction/signal/decision) is returned

    The session carries:
        - Request parameters (symbols, universe, timeframe)
        - Authentication context
        - Processing metadata
        - Timing information
        - Result references
    """

    session_id: str = field(default_factory=lambda: f"ais_{uuid4().hex[:16]}")
    mode: Optional["AIPlatformMode"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Request parameters
    symbols: List[str] = field(default_factory=list)
    universe: Optional[str] = None
    timeframe: Optional[str] = None
    query: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None

    # Status
    is_active: bool = True
    result_references: List[str] = field(default_factory=list)

    async def close(self) -> None:
        """Close the session."""
        self.is_active = False
        self.closed_at = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> float:
        """Session duration in seconds."""
        end = self.closed_at or datetime.now(timezone.utc)
        return (end - self.created_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "mode": str(self.mode) if self.mode else None,
            "symbols": self.symbols,
            "universe": self.universe,
            "timeframe": self.timeframe,
            "query": self.query,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "duration_seconds": self.duration_seconds,
        }

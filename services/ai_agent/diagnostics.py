"""
Diagnostics utilities for AI Agent troubleshooting.

Provides system state inspection, performance profiling,
error analysis, and diagnostic reporting capabilities.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Diagnostic Types ──


class DiagnosticLevel(str, Enum):
    """Diagnostic report severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DiagnosticEvent:
    """A recorded diagnostic event."""

    event_id: str = ""
    level: DiagnosticLevel = DiagnosticLevel.INFO
    category: str = ""
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceProfile:
    """Performance profiling snapshot."""

    name: str = ""
    total_calls: int = 0
    total_duration_seconds: float = 0.0
    min_duration_seconds: float = float("inf")
    max_duration_seconds: float = 0.0
    avg_duration_seconds: float = 0.0
    last_duration_seconds: float = 0.0

    def record(self, duration_seconds: float) -> None:
        """Record a new timing observation."""
        self.total_calls += 1
        self.total_duration_seconds += duration_seconds
        self.min_duration_seconds = min(self.min_duration_seconds, duration_seconds)
        self.max_duration_seconds = max(self.max_duration_seconds, duration_seconds)
        self.avg_duration_seconds = self.total_duration_seconds / self.total_calls
        self.last_duration_seconds = duration_seconds


# ── Agent Diagnostics ──


class AgentDiagnostics:
    """Diagnostics service for the AI Agent Platform.

    Provides system state inspection, performance profiling,
    error tracking, and diagnostic reporting.

    Usage:
        diag = AgentDiagnostics()
        diag.record_error("planning_timeout", "Planning exceeded time limit")
        profile = diag.profile_operation("reasoning")
        # ... run reasoning ...
        profile.record(elapsed_seconds)
        report = diag.generate_report()
    """

    def __init__(self, max_events: int = 1000) -> None:
        self.max_events = max_events
        self._events: List[DiagnosticEvent] = []
        self._profiles: Dict[str, PerformanceProfile] = {}
        self._error_count: int = 0
        self._warning_count: int = 0
        logger.info("AgentDiagnostics initialized")

    # ── Event Recording ──

    def record_event(
        self,
        category: str,
        message: str,
        level: DiagnosticLevel = DiagnosticLevel.INFO,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a diagnostic event.

        Args:
            category: Event category (e.g., "planning", "execution").
            message: Human-readable description.
            level: Severity level.
            details: Additional contextual data.
        """
        event = DiagnosticEvent(
            event_id=str(len(self._events)),
            level=level,
            category=category,
            message=message,
            details=details or {},
        )
        self._events.append(event)

        if level == DiagnosticLevel.ERROR:
            self._error_count += 1
            logger.error(f"[{category}] {message}")
        elif level == DiagnosticLevel.WARNING:
            self._warning_count += 1
            logger.warning(f"[{category}] {message}")
        else:
            logger.debug(f"[{category}] {message}")

        # Enforce max events
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events:]

    def record_error(
        self,
        category: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Shortcut for recording an error event."""
        self.record_event(
            category=category,
            message=message,
            level=DiagnosticLevel.ERROR,
            details=details,
        )

    def record_warning(
        self,
        category: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Shortcut for recording a warning event."""
        self.record_event(
            category=category,
            message=message,
            level=DiagnosticLevel.WARNING,
            details=details,
        )

    # ── Performance Profiling ──

    def profile_operation(self, name: str) -> PerformanceProfile:
        """Get or create a performance profile for an operation.

        Args:
            name: Operation name (e.g., "planning", "reasoning").

        Returns:
            PerformanceProfile for recording timings.
        """
        if name not in self._profiles:
            self._profiles[name] = PerformanceProfile(name=name)
        return self._profiles[name]

    def time_operation(self, name: str, duration_seconds: float) -> None:
        """Record a timing for an operation.

        Args:
            name: Operation name.
            duration_seconds: Duration to record.
        """
        profile = self.profile_operation(name)
        profile.record(duration_seconds)

    # ── Queries ──

    def get_events(
        self,
        level: Optional[DiagnosticLevel] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get diagnostic events with optional filtering.

        Args:
            level: Filter by severity.
            category: Filter by category.
            limit: Maximum events.

        Returns:
            List of event dicts.
        """
        events = self._events
        if level:
            events = [e for e in events if e.level == level]
        if category:
            events = [e for e in events if e.category == category]

        events = events[-limit:]
        return [
            {
                "event_id": e.event_id,
                "level": e.level.value,
                "category": e.category,
                "message": e.message,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ]

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Get performance profile for an operation.

        Args:
            name: Operation name.

        Returns:
            Profile data or None.
        """
        profile = self._profiles.get(name)
        if not profile:
            return None
        return {
            "name": profile.name,
            "total_calls": profile.total_calls,
            "avg_duration_seconds": profile.avg_duration_seconds,
            "min_duration_seconds": profile.min_duration_seconds,
            "max_duration_seconds": profile.max_duration_seconds,
            "last_duration_seconds": profile.last_duration_seconds,
        }

    def get_all_profiles(self) -> Dict[str, Any]:
        """Get all performance profiles."""
        return {
            name: self.get_profile(name)
            for name in self._profiles
        }

    # ── Reports ──

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive diagnostic report.

        Returns:
            Report dict with events, profiles, and summary.
        """
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_summary(),
            "profiles": self.get_all_profiles(),
            "recent_errors": self.get_events(level=DiagnosticLevel.ERROR, limit=20),
            "recent_warnings": self.get_events(level=DiagnosticLevel.WARNING, limit=20),
        }

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get diagnostic summary."""
        return {
            "total_events": len(self._events),
            "error_count": self._error_count,
            "warning_count": self._warning_count,
            "profiled_operations": len(self._profiles),
        }

    def clear(self) -> None:
        """Clear all diagnostic data."""
        self._events.clear()
        self._profiles.clear()
        self._error_count = 0
        self._warning_count = 0
        logger.info("AgentDiagnostics cleared")

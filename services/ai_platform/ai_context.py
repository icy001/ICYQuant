"""AI Context — Unified context object carrying the complete AI decision state.

The AIContext is the core data object that flows through the entire AI platform.
It carries all information needed to make and audit an AI decision:
market data, research results, agent analysis, features, predictions,
signals, risk assessments, and the final decision.

Every AI decision can be traced back through this context object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .ai_session import AISession


class DecisionPhase(str, Enum):
    """Phases of AI decision-making."""

    OBSERVATION = "observation"
    RESEARCH = "research"
    HYPOTHESIS = "hypothesis"
    FEATURE = "feature"
    PREDICTION = "prediction"
    SIGNAL = "signal"
    STRATEGY = "strategy"
    RISK = "risk"
    DECISION = "decision"
    EXECUTION = "execution"


@dataclass
class DecisionComponent:
    """A component of the AI decision."""

    phase: DecisionPhase
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIContext:
    """AI Context — unified context for AI decisions.

    This is the central data structure that flows through the entire
    AI pipeline. It accumulates information at each stage and provides
    a complete audit trail for every AI decision.

    Architecture:
        DecisionContext
        ├── Market Context (prices, volumes, events)
        ├── Research Context (hypotheses, evidence)
        ├── Agent Context (agent analysis, opinions)
        ├── Feature Context (feature values, versions)
        ├── Model Context (model_id, version, prediction)
        ├── Portfolio Context (positions, exposures)
        ├── Risk Context (risk checks, limits)
        └── Execution Context (orders, fills)
    """

    session: AISession
    decision_id: str = ""
    phases: List[DecisionComponent] = field(default_factory=list)
    _data: Dict[str, Any] = field(default_factory=dict)
    _errors: List[str] = field(default_factory=list)
    _warnings: List[str] = field(default_factory=list)

    # Quick access flags
    has_signal: bool = False
    has_prediction: bool = False
    risk_approved: bool = False
    decision_approved: bool = False
    final_decision: Optional[str] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Context Categories
    # ------------------------------------------------------------------

    # Market Context
    market_data: Dict[str, Any] = field(default_factory=dict)

    # Research Context
    research_context: Dict[str, Any] = field(default_factory=dict)

    # Agent Context
    agent_context: Dict[str, Any] = field(default_factory=dict)

    # Feature Context
    feature_context: Dict[str, Any] = field(default_factory=dict)

    # Model Context
    model_context: Dict[str, Any] = field(default_factory=dict)

    # Portfolio Context
    portfolio_context: Dict[str, Any] = field(default_factory=dict)

    # Risk Context
    risk_context: Dict[str, Any] = field(default_factory=dict)

    # Execution Context
    execution_context: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Data Management
    # ------------------------------------------------------------------

    def set_data(self, key: str, value: Any) -> None:
        """Set arbitrary context data."""
        self._data[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get context data by key."""
        return self._data.get(key, default)

    def has_data(self, key: str) -> bool:
        """Check if data exists."""
        return key in self._data

    # ------------------------------------------------------------------
    # Phase Tracking
    # ------------------------------------------------------------------

    def add_phase(
        self,
        phase: DecisionPhase,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        confidence: float = 0.0,
        **metadata,
    ) -> DecisionComponent:
        """Record a decision phase."""
        component = DecisionComponent(
            phase=phase,
            input_data=input_data or {},
            output_data=output_data or {},
            confidence=confidence,
            metadata=metadata or {},
        )
        self.phases.append(component)

        if phase == DecisionPhase.PREDICTION:
            self.has_prediction = True
        elif phase == DecisionPhase.SIGNAL:
            self.has_signal = True

        self.updated_at = datetime.now(timezone.utc)
        return component

    def get_phase(self, phase: DecisionPhase) -> Optional[DecisionComponent]:
        """Get the last component for a given phase."""
        for component in reversed(self.phases):
            if component.phase == phase:
                return component
        return None

    # ------------------------------------------------------------------
    # Error & Warning Management
    # ------------------------------------------------------------------

    def add_error(self, error: str) -> None:
        """Add an error to the context."""
        self._errors.append(error)
        self.updated_at = datetime.now(timezone.utc)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the context."""
        self._warnings.append(warning)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def errors(self) -> List[str]:
        return list(self._errors)

    @property
    def warnings(self) -> List[str]:
        return list(self._warnings)

    @property
    def has_errors(self) -> bool:
        return len(self._errors) > 0

    # ------------------------------------------------------------------
    # Convenience Properties
    # ------------------------------------------------------------------

    @property
    def prediction(self) -> Optional[Any]:
        """Get the latest prediction."""
        return self.get_data("prediction") or self.get_data("model_prediction")

    @property
    def signal(self) -> Optional[Any]:
        """Get the latest signal."""
        return self.get_data("signal")

    @property
    def features(self) -> Optional[Any]:
        """Get the latest features."""
        return self.get_data("features") or self.get_data("feature_extraction")

    @property
    def research(self) -> Optional[Any]:
        """Get the latest research results."""
        return self.get_data("research")

    @property
    def agent_analysis(self) -> Optional[Any]:
        """Get the latest agent analysis."""
        return self.get_data("agent_analysis")

    @property
    def risk_assessment(self) -> Optional[Any]:
        """Get the latest risk assessment."""
        return self.get_data("risk_check")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_summary(self) -> Dict[str, Any]:
        """Get a summary of the context for logging/audit."""
        return {
            "decision_id": self.decision_id,
            "session_id": self.session.session_id,
            "mode": self.session.mode.value if hasattr(self.session.mode, 'value') else str(self.session.mode),
            "has_signal": self.has_signal,
            "has_prediction": self.has_prediction,
            "risk_approved": self.risk_approved,
            "decision_approved": self.decision_approved,
            "final_decision": self.final_decision,
            "phases": [p.phase.value for p in self.phases],
            "phase_count": len(self.phases),
            "errors": len(self._errors),
            "warnings": len(self._warnings),
            "data_keys": list(self._data.keys()),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full serialization."""
        return {
            "decision_id": self.decision_id,
            "session": {
                "session_id": self.session.session_id,
                "mode": str(self.session.mode),
            },
            "phases": [
                {
                    "phase": p.phase.value,
                    "timestamp": p.timestamp.isoformat(),
                    "confidence": p.confidence,
                    "input_keys": list(p.input_data.keys()),
                    "output_keys": list(p.output_data.keys()),
                    "metadata": p.metadata,
                }
                for p in self.phases
            ],
            "flags": {
                "has_signal": self.has_signal,
                "has_prediction": self.has_prediction,
                "risk_approved": self.risk_approved,
                "decision_approved": self.decision_approved,
            },
            "contexts": {
                "market": list(self.market_data.keys()),
                "research": list(self.research_context.keys()),
                "agent": list(self.agent_context.keys()),
                "feature": list(self.feature_context.keys()),
                "model": list(self.model_context.keys()),
                "portfolio": list(self.portfolio_context.keys()),
                "risk": list(self.risk_context.keys()),
                "execution": list(self.execution_context.keys()),
            },
            "errors": self._errors,
            "warnings": self._warnings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

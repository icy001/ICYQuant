"""Agent Organization Memory - institutional memory for multi-agent collaboration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import defaultdict


class MemoryEventType(Enum):
    """Type of organizational memory event."""
    CONVERSATION = "CONVERSATION"
    DECISION = "DECISION"
    OUTCOME = "OUTCOME"
    LESSON = "LESSON"
    WORKFLOW = "WORKFLOW"
    COLLABORATION = "COLLABORATION"
    CONFLICT = "CONFLICT"
    RESOLUTION = "RESOLUTION"
    INSIGHT = "INSIGHT"


class LessonCategory(Enum):
    """Category of organizational lesson."""
    PROCESS = "PROCESS"
    COMMUNICATION = "COMMUNICATION"
    DECISION_MAKING = "DECISION_MAKING"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    STRATEGY = "STRATEGY"
    EXECUTION = "EXECUTION"
    COLLABORATION = "COLLABORATION"


@dataclass
class OrganizationMemoryEntry:
    """A single entry in organization memory."""
    entry_id: str
    event_type: MemoryEventType
    agents_involved: List[str]
    description: str
    outcome: str
    lesson: str
    category: LessonCategory = LessonCategory.PROCESS
    importance: float = 0.5
    context: Dict[str, Any] = field(default_factory=dict)
    related_entries: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class CollaborationPattern:
    """Pattern identified in agent collaboration."""
    pattern_id: str
    pattern_name: str
    agents_involved: List[str]
    workflow_type: str
    success_rate: float
    avg_duration: float
    common_outcomes: List[str]
    improvement_suggestions: List[str]


@dataclass
class OrganizationKnowledge:
    """Aggregated organizational knowledge."""
    total_collaborations: int
    total_decisions: int
    total_lessons: int
    best_collaboration_patterns: List[str]
    top_lessons: List[str]
    team_strengths: List[str]
    team_weaknesses: List[str]
    recommendations: List[str]


class AgentOrganizationMemory:
    """Organizational memory for multi-agent systems.

    Preserves:
    - Conversations between agents
    - Collective decisions
    - Decision outcomes
    - Organizational lessons learned
    - Collaboration patterns

    Enables the organization to learn and improve over time.
    """

    def __init__(self):
        self.history: List[OrganizationMemoryEntry] = []
        self._patterns: Dict[str, CollaborationPattern] = {}
        self._lessons_by_category: Dict[LessonCategory, List[str]] = defaultdict(list)
        self._agent_collaborations: Dict[str, List[str]] = defaultdict(list)
        self._entry_counter = 0

    def save(self, event: OrganizationMemoryEntry):
        """Save an organization memory event."""
        self.history.append(event)
        self._lessons_by_category[event.category].append(event.lesson)

        for agent in event.agents_involved:
            for other in event.agents_involved:
                if agent != other and other not in self._agent_collaborations[agent]:
                    self._agent_collaborations[agent].append(other)

    def save_conversation(self, agents: List[str], description: str,
                          outcome: str, lesson: str = "") -> OrganizationMemoryEntry:
        """Save a conversation between agents."""
        self._entry_counter += 1
        entry = OrganizationMemoryEntry(
            entry_id=f"conv_{self._entry_counter}",
            event_type=MemoryEventType.CONVERSATION,
            agents_involved=agents,
            description=description,
            outcome=outcome,
            lesson=lesson or f"Conversation between {', '.join(agents)}: {outcome}",
            category=LessonCategory.COMMUNICATION,
        )
        self.save(entry)
        return entry

    def save_decision(self, agents: List[str], description: str,
                      outcome: str, lesson: str = "") -> OrganizationMemoryEntry:
        """Save a collective decision."""
        self._entry_counter += 1
        entry = OrganizationMemoryEntry(
            entry_id=f"decision_{self._entry_counter}",
            event_type=MemoryEventType.DECISION,
            agents_involved=agents,
            description=description,
            outcome=outcome,
            lesson=lesson or f"Decision made by {', '.join(agents)}: {outcome}",
            category=LessonCategory.DECISION_MAKING,
            importance=0.8,
        )
        self.save(entry)
        return entry

    def save_outcome(self, agents: List[str], description: str,
                     outcome: str, lesson: str = "") -> OrganizationMemoryEntry:
        """Save a decision outcome."""
        self._entry_counter += 1
        entry = OrganizationMemoryEntry(
            entry_id=f"outcome_{self._entry_counter}",
            event_type=MemoryEventType.OUTCOME,
            agents_involved=agents,
            description=description,
            outcome=outcome,
            lesson=lesson or f"Outcome from {', '.join(agents)}: {outcome}",
            category=LessonCategory.EXECUTION,
            importance=0.7,
        )
        self.save(entry)
        return entry

    def save_lesson(self, agents: List[str], description: str,
                    lesson: str, category: LessonCategory = LessonCategory.PROCESS) -> OrganizationMemoryEntry:
        """Save an organizational lesson."""
        self._entry_counter += 1
        entry = OrganizationMemoryEntry(
            entry_id=f"lesson_{self._entry_counter}",
            event_type=MemoryEventType.LESSON,
            agents_involved=agents,
            description=description,
            outcome="Lesson recorded",
            lesson=lesson,
            category=category,
            importance=0.9,
        )
        self.save(entry)
        return entry

    def get_lessons(self, category: LessonCategory = None, limit: int = 20) -> List[str]:
        """Get lessons learned, optionally filtered by category."""
        if category:
            return self._lessons_by_category.get(category, [])[-limit:]
        all_lessons = []
        for cats in self._lessons_by_category.values():
            all_lessons.extend(cats)
        return all_lessons[-limit:]

    def get_decisions(self) -> List[OrganizationMemoryEntry]:
        """Get all organizational decisions."""
        return [e for e in self.history if e.event_type == MemoryEventType.DECISION]

    def get_outcomes(self) -> List[OrganizationMemoryEntry]:
        """Get all decision outcomes."""
        return [e for e in self.history if e.event_type == MemoryEventType.OUTCOME]

    def discover_collaboration_patterns(self) -> List[CollaborationPattern]:
        """Discover patterns in agent collaboration history."""
        patterns = []

        # Group entries by agents involved
        agent_groups = defaultdict(list)
        for entry in self.history:
            key = tuple(sorted(entry.agents_involved))
            agent_groups[key].append(entry)

        for agents_tuple, entries in agent_groups.items():
            if len(entries) >= 2:
                success_count = sum(1 for e in entries if "success" in e.outcome.lower() or "positive" in e.outcome.lower())
                pattern = CollaborationPattern(
                    pattern_id=f"pattern_{len(patterns)}",
                    pattern_name=f"Collaboration: {' + '.join(agents_tuple)}",
                    agents_involved=list(agents_tuple),
                    workflow_type=entries[0].event_type.value,
                    success_rate=success_count / len(entries),
                    avg_duration=0,
                    common_outcomes=list(set(e.outcome for e in entries)),
                    improvement_suggestions=[],
                )
                patterns.append(pattern)

        return patterns

    def get_knowledge_summary(self) -> OrganizationKnowledge:
        """Get aggregated organizational knowledge summary."""
        collaborations = sum(1 for e in self.history if e.event_type == MemoryEventType.COLLABORATION)
        decisions = sum(1 for e in self.history if e.event_type == MemoryEventType.DECISION)
        lessons = sum(1 for e in self.history if e.event_type == MemoryEventType.LESSON)

        # Find top collaboration patterns
        patterns = self.discover_collaboration_patterns()
        best_patterns = [p.pattern_name for p in sorted(patterns, key=lambda p: p.success_rate, reverse=True)[:3]]

        return OrganizationKnowledge(
            total_collaborations=collaborations,
            total_decisions=decisions,
            total_lessons=lessons,
            best_collaboration_patterns=best_patterns,
            top_lessons=self.get_lessons(limit=5),
            team_strengths=self._identify_strengths(),
            team_weaknesses=self._identify_weaknesses(),
            recommendations=self._generate_recommendations(),
        )

    def get_agent_collaboration_graph(self) -> Dict[str, List[str]]:
        """Get the collaboration network between agents."""
        return dict(self._agent_collaborations)

    def _identify_strengths(self) -> List[str]:
        """Identify organizational strengths from history."""
        strengths = []
        patterns = self.discover_collaboration_patterns()
        for p in patterns:
            if p.success_rate >= 0.8:
                strengths.append(f"Strong collaboration: {p.pattern_name} (success rate: {p.success_rate:.0%})")
        if not strengths:
            strengths.append("Organization is building its collaboration history")
        return strengths

    def _identify_weaknesses(self) -> List[str]:
        """Identify organizational weaknesses from history."""
        weaknesses = []
        patterns = self.discover_collaboration_patterns()
        for p in patterns:
            if p.success_rate < 0.4:
                weaknesses.append(f"Improvement needed: {p.pattern_name} (success rate: {p.success_rate:.0%})")
        if not weaknesses and self.history:
            weaknesses.append("Insufficient data to identify weaknesses")
        return weaknesses

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations for organizational improvement."""
        recommendations = []
        lessons = self.get_lessons()
        if lessons:
            recommendations.append(f"Apply lesson: {lessons[-1]}")
        if len(self.history) > 10:
            recommendations.append("Review historical patterns for process optimization")
        else:
            recommendations.append("Continue building collaboration history for better insights")
        return recommendations

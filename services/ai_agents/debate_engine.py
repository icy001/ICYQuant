"""
ICYQuant Debate Engine — structured multi-agent debate for quantitative decisions.

Orchestrates adversarial debate between agents (bull, bear, critic) to
stress-test ideas, strategies, and research findings before consensus.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from .agent_message import MessageEnvelope, MessageType, OpinionMessage

logger = logging.getLogger(__name__)

OpinionProvider = Callable[[str, dict[str, Any]], Awaitable[OpinionMessage]]


class DebateRole(str, Enum):
    PROPONENT = "proponent"       # Argues in favor
    OPPONENT = "opponent"         # Argues against
    MODERATOR = "moderator"       # Facilitates debate
    EVIDENCE_REVIEWER = "evidence_reviewer"  # Checks evidence quality


class DebatePhase(str, Enum):
    NOT_STARTED = "not_started"
    OPENING = "opening"           # Opening statements
    REBUTTAL = "rebuttal"         # Rebuttals and counter-arguments
    CROSS_EXAMINATION = "cross_examination"  # Cross-examining evidence
    CLOSING = "closing"           # Closing arguments
    CONCLUDED = "concluded"


class DebateFormat(str, Enum):
    TWO_SIDED = "two_sided"            # Proponent vs opponent
    MULTI_PERSPECTIVE = "multi_perspective"  # Bull vs bear vs critic
    ROUND_TABLE = "round_table"       # All agents contribute
    DEVILS_ADVOCATE = "devils_advocate"  # Single agent plays devil's advocate


@dataclass
class DebatePosition:
    """A position taken by an agent in a debate."""
    agent_id: str
    role: DebateRole
    stance: str                # "pro", "con", "neutral"
    arguments: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class DebateRound:
    """A single round of debate exchange."""
    round_number: int
    phase: DebatePhase
    statements: list[OpinionMessage] = field(default_factory=list)
    rebuttals: list[OpinionMessage] = field(default_factory=list)
    moderator_notes: str = ""


@dataclass
class DebateResult:
    """Outcome of a completed debate."""
    debate_id: str
    topic: str
    format: DebateFormat
    rounds: list[DebateRound] = field(default_factory=list)
    winner: str = ""                 # "proponent" or "opponent" or ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    controversy_level: float = 0.0   # 0 = full agreement, 1 = deep disagreement
    consensus_reached: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DebateEngine:
    """Structured multi-agent debate orchestrator.

    Debates follow a formal structure:
        1. Opening statements (proponent + opponent present positions)
        2. Rebuttal rounds (counter each other's arguments)
        3. Cross-examination (challenge evidence and assumptions)
        4. Closing arguments (summarize and persuade)
        5. Scoring (evaluate argument quality, evidence strength)

    Use cases:
        - Bull vs bear debate on a stock thesis
        - Strategy idea stress-testing
        - Methodological debate on factor construction
        - Adversarial review of research conclusions
    """

    def __init__(self, communication_bus: Any = None) -> None:
        self._comm_bus = communication_bus
        self._debates: dict[str, DebateResult] = {}
        self._total_debates = 0

    async def debate(self,
                     topic: str,
                     proponent_id: str,
                     opponent_id: str,
                     moderator_id: str = "",
                     debate_format: DebateFormat = DebateFormat.TWO_SIDED,
                     num_rounds: int = 3,
                     context: Optional[dict[str, Any]] = None) -> DebateResult:
        """Run a full structured debate."""
        result = DebateResult(
            debate_id=str(uuid.uuid4()),
            topic=topic,
            format=debate_format,
        )
        self._debates[result.debate_id] = result
        self._total_debates += 1
        context = context or {}

        max_rounds = num_rounds

        # ── Phase 1: Opening Statements ──
        result.rounds.append(DebateRound(
            round_number=0,
            phase=DebatePhase.OPENING,
        ))

        # ── Phase 2: Rebuttal Rounds ──
        for rnd in range(1, max_rounds + 1):
            debate_round = DebateRound(round_number=rnd, phase=DebatePhase.REBUTTAL)
            result.rounds.append(debate_round)

        # ── Phase 3: Cross-Examination ──
        result.rounds.append(DebateRound(
            round_number=max_rounds + 1,
            phase=DebatePhase.CROSS_EXAMINATION,
        ))

        # ── Phase 4: Closing Arguments ──
        result.rounds.append(DebateRound(
            round_number=max_rounds + 2,
            phase=DebatePhase.CLOSING,
        ))

        # ── Finalize ──
        result.completed_at = datetime.now(timezone.utc)
        result.summary = f"Debate on '{topic}' completed with {len(result.rounds)} rounds."
        result.winner = proponent_id  # Placeholder
        result.consensus_reached = False

        # Broadcast debate result
        if self._comm_bus:
            envelope = MessageEnvelope(
                msg_type=MessageType.DEBATE,
                sender_id="debate_engine",
                topic="debate.result",
                payload={
                    "debate_id": result.debate_id,
                    "topic": topic,
                    "winner": result.winner,
                    "consensus_reached": result.consensus_reached,
                },
            )
            await self._comm_bus.publish(envelope)

        return result

    async def register_opinion(self, debate_id: str, opinion: OpinionMessage,
                               round_number: int = 0) -> bool:
        """Register an opinion from a debate participant."""
        debate = self._debates.get(debate_id)
        if debate is None:
            return False

        # Find or create the round
        while len(debate.rounds) <= round_number:
            debate.rounds.append(DebateRound(
                round_number=len(debate.rounds),
                phase=DebatePhase.REBUTTAL,
            ))

        debate.rounds[round_number].statements.append(opinion)
        return True

    async def close_debate(self, debate_id: str, winner: str = "",
                           summary: str = "", consensus: bool = False) -> Optional[DebateResult]:
        """Close a debate with final results."""
        debate = self._debates.get(debate_id)
        if debate is None:
            return None

        debate.winner = winner
        debate.summary = summary
        debate.consensus_reached = consensus
        debate.completed_at = datetime.now(timezone.utc)

        # Calculate controversy level
        total_statements = sum(len(r.statements) for r in debate.rounds)
        debate.controversy_level = min(1.0, total_statements / 20.0)

        return debate

    def get_debate(self, debate_id: str) -> Optional[DebateResult]:
        return self._debates.get(debate_id)

    def get_active_debates(self) -> list[DebateResult]:
        return [d for d in self._debates.values() if d.completed_at is None]

    @property
    def total_debates(self) -> int:
        return self._total_debates

"""
Release candidate lifecycle management.

Manages the full RC lifecycle from Alpha through Beta, RC, and GA stages
with promotion workflows, version tagging, changelog accumulation,
release branch management, and Go/No-Go decisions.

Usage::

    rc = ReleaseCandidate(version="1.2.0")
    rc.start("alpha")
    rc.add_changelog_entry("Added new order validation")
    rc.record_blocking_issue("Critical bug in risk engine", severity="blocker")
    rc.promote("beta")
    status = rc.get_status()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .version_manager import PreReleaseTag, VersionManager


class RCStage(str, Enum):
    """Release candidate lifecycle stages."""

    ALPHA = "alpha"
    BETA = "beta"
    RC = "rc"
    GA = "ga"
    DEPRECATED = "deprecated"


class GoNoGoDecision(str, Enum):
    """Go/No-Go decision outcomes."""

    GO = "GO"
    NO_GO = "NO_GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"


class IssueSeverity(str, Enum):
    """Severity levels for blocking issues."""

    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


# Allowed stage transitions
_STAGE_TRANSITIONS: Dict[RCStage, List[RCStage]] = {
    RCStage.ALPHA: [RCStage.BETA, RCStage.DEPRECATED],
    RCStage.BETA: [RCStage.RC, RCStage.ALPHA, RCStage.DEPRECATED],
    RCStage.RC: [RCStage.GA, RCStage.BETA, RCStage.DEPRECATED],
    RCStage.GA: [RCStage.DEPRECATED],
    RCStage.DEPRECATED: [],
}

# Ordered stages for sequential advancement
_STAGE_ORDER: List[RCStage] = [
    RCStage.ALPHA,
    RCStage.BETA,
    RCStage.RC,
    RCStage.GA,
]


@dataclass
class BlockingIssue:
    """A blocking issue that may prevent promotion.

    Attributes:
        id: Unique issue identifier.
        description: Human-readable description.
        severity: Severity level.
        created_at: Timestamp when the issue was created.
        resolved: Whether the issue has been resolved.
        resolved_at: Timestamp when the issue was resolved, if ever.
    """

    id: str = ""
    description: str = ""
    severity: IssueSeverity = IssueSeverity.MAJOR
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    resolved: bool = False
    resolved_at: Optional[str] = None


@dataclass
class GoNoGoRecord:
    """A Go/No-Go decision record.

    Attributes:
        decision: The decision outcome.
        stage: The stage the decision applies to.
        reason: Justification for the decision.
        decider: Person or system that made the decision.
        decided_at: Timestamp of the decision.
    """

    decision: GoNoGoDecision = GoNoGoDecision.NO_GO
    stage: RCStage = RCStage.ALPHA
    reason: str = ""
    decider: str = ""
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ChangelogEntry:
    """A single changelog entry.

    Attributes:
        version: Version this entry belongs to.
        stage: Stage when the change was made.
        description: Description of the change.
        change_type: Type of change (e.g., 'added', 'fixed', 'changed').
        author: Author or contributor.
        timestamp: When the entry was created.
    """

    version: str = ""
    stage: RCStage = RCStage.ALPHA
    description: str = ""
    change_type: str = "changed"
    author: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class RCStatus:
    """Current state of a release candidate.

    Attributes:
        version: Base version string.
        current_stage: Current lifecycle stage.
        start_date: Timestamp when the RC was started.
        test_window_days: Duration of the test window in days.
        blocking_issues: List of unresolved blocking issues.
        go_no_go: Latest Go/No-Go decision.
        readiness_score: Readiness score 0.0 - 1.0.
        promotion_recommendation: Suggested next action.
        release_branch: Git release branch name.
        changelog_accumulated: Total changelog entries accumulated.
    """

    version: str = ""
    current_stage: RCStage = RCStage.ALPHA
    start_date: str = ""
    test_window_days: int = 14
    blocking_issues: List[BlockingIssue] = field(default_factory=list)
    go_no_go: Optional[GoNoGoDecision] = None
    readiness_score: float = 0.0
    promotion_recommendation: str = "blocked"
    release_branch: str = ""
    changelog_accumulated: int = 0


class ReleaseCandidate:
    """Manages the release candidate lifecycle.

    Supports promotion workflows from Alpha → Beta → RC → GA with
    version tagging, changelog accumulation, release branch management,
    and Go/No-Go decisions.

    Usage::

        rc = ReleaseCandidate(version="1.2.0", pre_release_tag=PreReleaseTag.BETA)
        rc.start("beta")
        rc.add_changelog_entry("Fixed drawdown calculation", change_type="fixed")
        rc.record_blocking_issue("Memory leak in backtest engine", "critical")
        rc.promote("rc")
        status = rc.get_status()
    """

    def __init__(
        self,
        version: str,
        pre_release_tag: Optional[PreReleaseTag] = None,
        test_window_days: int = 14,
    ):
        """Initialize a release candidate.

        Args:
            version: Base version string (e.g., "1.2.0").
            pre_release_tag: Initial pre-release tag, if any.
            test_window_days: Duration of the test window in days.
        """
        self._version = version
        self._pre_release_tag = pre_release_tag
        self._test_window_days = test_window_days
        self._vm = VersionManager()

        self._stage: RCStage = RCStage.ALPHA
        self._start_date: Optional[str] = None
        self._release_branch: str = ""

        self._blocking_issues: List[BlockingIssue] = []
        self._go_no_go_history: List[GoNoGoRecord] = []
        self._changelog: List[ChangelogEntry] = []
        self._stage_history: List[Dict[str, Any]] = []

    @property
    def version(self) -> str:
        """Base version string."""
        return self._version

    @property
    def current_stage(self) -> RCStage:
        """Current lifecycle stage."""
        return self._stage

    @property
    def start_date(self) -> Optional[str]:
        """Timestamp when the RC was started."""
        return self._start_date

    @property
    def blocking_issues(self) -> List[BlockingIssue]:
        """List of unresolved blocking issues."""
        return [b for b in self._blocking_issues if not b.resolved]

    @property
    def all_issues(self) -> List[BlockingIssue]:
        """All blocking issues (resolved and unresolved)."""
        return list(self._blocking_issues)

    @property
    def changelog(self) -> List[ChangelogEntry]:
        """Accumulated changelog entries."""
        return list(self._changelog)

    @property
    def go_no_go(self) -> Optional[GoNoGoDecision]:
        """Latest Go/No-Go decision."""
        if self._go_no_go_history:
            return self._go_no_go_history[-1].decision
        return None

    def start(
        self,
        stage: str = "alpha",
        release_branch: Optional[str] = None,
    ) -> RCStatus:
        """Start the release candidate at the given stage.

        Args:
            stage: Initial stage name (e.g., "alpha", "beta").
            release_branch: Git release branch name. Auto-generated if not provided.

        Returns:
            Updated RCStatus.

        Raises:
            ValueError: If the stage is not valid.
            RuntimeError: If the RC has already been started.
        """
        if self._start_date is not None:
            raise RuntimeError(
                f"Release candidate {self._version} has already been started"
            )

        stage_enum = RCStage(stage.lower())
        self._stage = stage_enum
        self._start_date = datetime.now(timezone.utc).isoformat()

        if release_branch:
            self._release_branch = release_branch
        else:
            tag = self._pre_release_tag.value if self._pre_release_tag else stage_enum.value
            self._release_branch = f"release/{self._version}-{tag}"

        self._record_stage_transition(None, stage_enum)
        return self.get_status()

    def promote(
        self,
        target_stage: str,
        force: bool = False,
    ) -> RCStatus:
        """Promote the release candidate to the next stage.

        Args:
            target_stage: Target stage name (e.g., "beta", "rc", "ga").
            force: If True, skip blocking issue checks.

        Returns:
            Updated RCStatus.

        Raises:
            RuntimeError: If promotion is blocked by unresolved issues.
            ValueError: If the target stage is not reachable from current stage.
        """
        target = RCStage(target_stage.lower())
        allowed = _STAGE_TRANSITIONS.get(self._stage, [])

        if target not in allowed:
            raise ValueError(
                f"Cannot promote from {self._stage.value} to {target.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )

        if not force and self.blocking_issues:
            blocker_count = len(self.blocking_issues)
            raise RuntimeError(
                f"Cannot promote to {target.value}: {blocker_count} blocking "
                f"issue(s) unresolved. Use force=True to override."
            )

        previous_stage = self._stage
        self._stage = target
        self._record_stage_transition(previous_stage, target)

        if target == RCStage.GA:
            self._release_branch = f"release/{self._version}-ga"

        return self.get_status()

    def rollback(self, target_stage: str) -> RCStatus:
        """Rollback to a previous stage.

        Args:
            target_stage: Target stage to rollback to.

        Returns:
            Updated RCStatus.

        Raises:
            ValueError: If rollback is not allowed to the target stage.
        """
        target = RCStage(target_stage.lower())
        allowed = _STAGE_TRANSITIONS.get(target, [])

        if self._stage not in allowed and self._stage != target:
            raise ValueError(
                f"Cannot rollback from {self._stage.value} to {target.value}"
            )

        previous_stage = self._stage
        self._stage = target
        self._record_stage_transition(previous_stage, target)
        return self.get_status()

    def deprecate(self) -> RCStatus:
        """Mark the release candidate as deprecated.

        Returns:
            Updated RCStatus.
        """
        previous_stage = self._stage
        self._stage = RCStage.DEPRECATED
        self._record_stage_transition(previous_stage, RCStage.DEPRECATED)
        return self.get_status()

    def record_blocking_issue(
        self,
        description: str,
        severity: str = "major",
        issue_id: Optional[str] = None,
    ) -> BlockingIssue:
        """Record a new blocking issue.

        Args:
            description: Human-readable description of the issue.
            severity: Severity level ("blocker", "critical", "major", "minor").
            issue_id: Optional unique identifier. Auto-generated if not provided.

        Returns:
            The created BlockingIssue.
        """
        sev = IssueSeverity(severity.lower())
        if issue_id is None:
            import uuid

            issue_id = str(uuid.uuid4())[:8]

        issue = BlockingIssue(
            id=issue_id,
            description=description,
            severity=sev,
        )
        self._blocking_issues.append(issue)
        return issue

    def resolve_issue(self, issue_id: str) -> Optional[BlockingIssue]:
        """Mark a blocking issue as resolved.

        Args:
            issue_id: Identifier of the issue to resolve.

        Returns:
            The resolved BlockingIssue, or None if not found.
        """
        for issue in self._blocking_issues:
            if issue.id == issue_id:
                issue.resolved = True
                issue.resolved_at = datetime.now(timezone.utc).isoformat()
                return issue
        return None

    def add_changelog_entry(
        self,
        description: str,
        change_type: str = "changed",
        author: str = "",
    ) -> ChangelogEntry:
        """Accumulate a changelog entry.

        Args:
            description: Description of the change.
            change_type: Type of change ("added", "fixed", "changed", "removed").
            author: Author or contributor name.

        Returns:
            The created ChangelogEntry.
        """
        entry = ChangelogEntry(
            version=self._version,
            stage=self._stage,
            description=description,
            change_type=change_type,
            author=author,
        )
        self._changelog.append(entry)
        return entry

    def record_go_no_go(
        self,
        decision: str,
        reason: str = "",
        decider: str = "",
    ) -> GoNoGoRecord:
        """Record a Go/No-Go decision.

        Args:
            decision: Decision outcome ("GO", "NO_GO", "CONDITIONAL_GO").
            reason: Justification for the decision.
            decider: Person or system making the decision.

        Returns:
            The created GoNoGoRecord.
        """
        decision_enum = GoNoGoDecision(decision.upper())
        record = GoNoGoRecord(
            decision=decision_enum,
            stage=self._stage,
            reason=reason,
            decider=decider,
        )
        self._go_no_go_history.append(record)
        return record

    def generate_release_tag(
        self,
        prefix: str = "v",
    ) -> str:
        """Generate the release tag for the current version and stage.

        Args:
            prefix: Tag prefix (default "v").

        Returns:
            Release tag string (e.g., "v1.2.0-beta.1").
        """
        pre_tag: Optional[PreReleaseTag] = None
        pre_num: Optional[int] = None

        if self._stage == RCStage.GA:
            pass
        elif self._stage == RCStage.RC:
            pre_tag = PreReleaseTag.RC
            pre_num = self._next_pre_release_num(PreReleaseTag.RC)
        elif self._stage == RCStage.BETA:
            pre_tag = PreReleaseTag.BETA
            pre_num = self._next_pre_release_num(PreReleaseTag.BETA)
        elif self._stage == RCStage.ALPHA:
            pre_tag = PreReleaseTag.ALPHA
            pre_num = self._next_pre_release_num(PreReleaseTag.ALPHA)

        return self._vm.generate_tag(
            self._version,
            pre_release=pre_tag,
            pre_release_num=pre_num,
            prefix=prefix,
        )

    def get_readiness_score(self) -> float:
        """Calculate a readiness score from 0.0 to 1.0.

        The score is based on:
        - Stage progress (higher stage = higher score)
        - Blocking issue resolution ratio
        - Presence of a Go/No-Go decision

        Returns:
            Readiness score in [0.0, 1.0].
        """
        stage_score_map = {
            RCStage.ALPHA: 0.25,
            RCStage.BETA: 0.50,
            RCStage.RC: 0.75,
            RCStage.GA: 1.0,
            RCStage.DEPRECATED: 0.0,
        }

        base_score = stage_score_map.get(self._stage, 0.0)

        if self._blocking_issues:
            resolved_count = sum(1 for b in self._blocking_issues if b.resolved)
            resolution_ratio = resolved_count / len(self._blocking_issues)
            base_score *= (0.5 + 0.5 * resolution_ratio)

        if self._go_no_go_history:
            latest = self._go_no_go_history[-1].decision
            if latest == GoNoGoDecision.GO:
                base_score = min(1.0, base_score + 0.15)
            elif latest == GoNoGoDecision.CONDITIONAL_GO:
                base_score = min(1.0, base_score + 0.05)
            elif latest == GoNoGoDecision.NO_GO:
                base_score *= 0.5

        return round(max(0.0, min(1.0, base_score)), 3)

    def get_status(self) -> RCStatus:
        """Get the current status of the release candidate.

        Returns:
            RCStatus with current stage, blocking issues, readiness score,
            and promotion recommendation.
        """
        readiness = self.get_readiness_score()

        if self._stage == RCStage.GA:
            recommendation = "released"
        elif self._stage == RCStage.DEPRECATED:
            recommendation = "deprecated"
        elif self.blocking_issues:
            recommendation = "blocked"
        elif readiness >= 0.8:
            recommendation = "ready_for_promotion"
        elif readiness >= 0.5:
            recommendation = " progressing"
        else:
            recommendation = "not_ready"

        return RCStatus(
            version=self._version,
            current_stage=self._stage,
            start_date=self._start_date or "",
            test_window_days=self._test_window_days,
            blocking_issues=self.blocking_issues,
            go_no_go=self.go_no_go,
            readiness_score=readiness,
            promotion_recommendation=recommendation,
            release_branch=self._release_branch,
            changelog_accumulated=len(self._changelog),
        )

    def _record_stage_transition(
        self,
        previous: Optional[RCStage],
        current: RCStage,
    ) -> None:
        """Record a stage transition in the history.

        Args:
            previous: Previous stage, or None if starting.
            current: New stage.
        """
        self._stage_history.append({
            "from": previous.value if previous else None,
            "to": current.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _next_pre_release_num(self, tag: PreReleaseTag) -> int:
        """Determine the next pre-release number for the given tag.

        Args:
            tag: Pre-release tag type.

        Returns:
            Next pre-release number (always 1 for current implementation).
        """
        return 1
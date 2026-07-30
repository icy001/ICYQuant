"""
ICYQuant Release Candidate Package.

Provides release candidate lifecycle management including version management,
RC state tracking, and validation gates for promotion from Alpha → Beta → RC → GA.
"""

from .version_manager import (
    PreReleaseTag,
    VersionInfo,
    VersionManager,
)

from .release_candidate import (
    RCStage,
    GoNoGoDecision,
    IssueSeverity,
    BlockingIssue,
    GoNoGoRecord,
    ChangelogEntry,
    RCStatus,
    ReleaseCandidate,
)

from .rc_validator import (
    ValidationGate,
    GateStatus,
    GateResult,
    RCValidationResult,
    RCValidator,
)

__all__ = [
    "PreReleaseTag",
    "VersionInfo",
    "VersionManager",
    "RCStage",
    "GoNoGoDecision",
    "IssueSeverity",
    "BlockingIssue",
    "GoNoGoRecord",
    "ChangelogEntry",
    "RCStatus",
    "ReleaseCandidate",
    "ValidationGate",
    "GateStatus",
    "GateResult",
    "RCValidationResult",
    "RCValidator",
]
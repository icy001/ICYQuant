"""Candidate model and lifecycle for Strategy Discovery Lab v1.

A Candidate is a *fully reproducible* strategy definition — it records the
strategy ID, family, structure, exact parameters, entry/exit rule text, the
asset, timeframe, dataset version and cost model. Every result produced by the
Discovery Lab is traceable back to this definition; nothing like "this strategy
looked good" is ever stored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

from .spec import DISCOVERY_SPEC_V1, STRUCTURES

DATASET_VERSION = "research-universe-v1.1"


class CandidateFamily(str, Enum):
    TREND = "Trend"
    MOMENTUM = "Momentum"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"
    HYBRID = "Hybrid"


class CandidateStatus(str, Enum):
    """Candidate lifecycle (v1). Failed candidates keep their reject reason."""

    GENERATED = "GENERATED"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    OOS_TESTED = "OOS_TESTED"
    ROBUSTNESS_TESTED = "ROBUSTNESS_TESTED"
    CANDIDATE = "CANDIDATE"
    REJECTED = "REJECTED"


class CandidateLifecycle(str, Enum):
    """The full promotion chain (future pipeline stages)."""

    GENERATED = "GENERATED"
    BACKTESTED = "BACKTESTED"
    VALIDATED = "VALIDATED"
    OOS_TESTED = "OOS_TESTED"
    ROBUSTNESS_TESTED = "ROBUSTNESS_TESTED"
    CANDIDATE = "CANDIDATE"
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    PRODUCTION = "PRODUCTION"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Candidate:
    """A sealed, reproducible strategy definition."""

    candidate_id: str                       # e.g. "C0001"
    family: str                             # CandidateFamily value
    structure_id: str                       # key into STRUCTURES
    parameters: dict[str, Any]              # exact parameter values
    asset: str                              # universe symbol
    timeframe: str                          # "1H"
    dataset_version: str = DATASET_VERSION
    spec_version: str = "v1"
    entry_rule: str = ""
    exit_rule: str = ""
    description: str = ""
    status: str = CandidateStatus.GENERATED.value
    reject_reason: Optional[str] = None

    # --- construction ------------------------------------------------------ #

    @classmethod
    def build(cls, candidate_id: str, structure_id: str, parameters: dict[str, Any],
              asset: str, timeframe: str = "1H") -> "Candidate":
        struct = STRUCTURES[structure_id]
        return cls(
            candidate_id=candidate_id,
            family=struct["family"],
            structure_id=structure_id,
            parameters=dict(parameters),
            asset=asset,
            timeframe=timeframe,
            entry_rule=struct["entry"],
            exit_rule=struct["exit"],
            description=struct["description"],
        )

    # --- serialization ----------------------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        return cls(**data)

    @classmethod
    def from_json(cls, text: str) -> "Candidate":
        return cls.from_dict(json.loads(text))


@dataclass(frozen=True)
class CandidateManifest:
    """The full list of generated candidates plus the sealed spec snapshot."""

    spec: dict[str, Any]
    generated_at: str
    candidates: list[Candidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec,
            "generated_at": self.generated_at,
            "candidates": [c.to_dict() for c in self.candidates],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


__all__ = [
    "Candidate", "CandidateManifest", "CandidateFamily",
    "CandidateStatus", "CandidateLifecycle", "DATASET_VERSION",
]

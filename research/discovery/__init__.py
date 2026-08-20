"""Strategy Discovery Lab v1.

ICYQuant's autonomous strategy-discovery capability. Given a fixed research
universe and a bounded search space (families / structures / parameter grids),
the Discovery Lab:

    generate 300 reproducible candidates
        -> backtest each on 9 assets x 1H
        -> Train / Validation / OOS isolation
        -> robustness (parameter stability + walk-forward)
        -> multi-factor ranking
        -> Discovery Gate v1 (16 checks)
        -> Discovery Report (top candidates + family analysis)

Hard rules (immutable for v1):
    - OOS data is NEVER used for parameter selection.
    - A failing OOS check rejects the candidate (no rescue by other metrics).
    - Candidates are ranked by a multi-factor score, never by return alone.
    - Transaction costs (commission + spread + slippage) are always included.
    - The Gate thresholds are fixed once Discovery Specification v1 is sealed.
"""
from __future__ import annotations

from .spec import (
    DISCOVERY_SPEC_V1,
    DiscoverySpec,
    GATE_THRESHOLDS,
    SCORE_WEIGHTS,
    SPLIT_CONFIG,
    COST_CONFIG,
    STRUCTURES,
    PARAMETER_SPACES,
    FAMILY_NAMES,
)
from .candidate import (
    Candidate,
    CandidateStatus,
    CandidateLifecycle,
    CandidateFamily,
)
from .indicators import IndicatorLibrary
from .split import TimeSplit, SPLITS, ACTIVE_SPLIT, WalkForwardWindow
from .backtest import (
    DiscoveryBacktest,
    BacktestResult,
    TradeRecord,
    Metrics,
)
from .generator import CandidateGenerator
from .cost import CostModel
from .robustness import (
    parameter_stability,
    walk_forward_check,
    StabilityReport,
)
from .ranking import rank_candidates, DiscoveryScore
from .gate import DiscoveryGate, GateOutcome, GateCheck
from .engine import DiscoveryEngine, DiscoveryExperimentResult
from .report import DiscoveryReport

__all__ = [
    "DISCOVERY_SPEC_V1",
    "DiscoverySpec",
    "GATE_THRESHOLDS",
    "SCORE_WEIGHTS",
    "SPLIT_CONFIG",
    "COST_CONFIG",
    "STRUCTURES",
    "PARAMETER_SPACES",
    "FAMILY_NAMES",
    "Candidate",
    "CandidateStatus",
    "CandidateLifecycle",
    "CandidateFamily",
    "IndicatorLibrary",
    "TimeSplit",
    "SPLITS",
    "ACTIVE_SPLIT",
    "WalkForwardWindow",
    "DiscoveryBacktest",
    "BacktestResult",
    "TradeRecord",
    "Metrics",
    "CandidateGenerator",
    "CostModel",
    "parameter_stability",
    "walk_forward_check",
    "StabilityReport",
    "rank_candidates",
    "DiscoveryScore",
    "DiscoveryGate",
    "GateOutcome",
    "GateCheck",
    "DiscoveryEngine",
    "DiscoveryExperimentResult",
    "DiscoveryReport",
]

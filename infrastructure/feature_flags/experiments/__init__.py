"""
Experiment framework for A/B testing.

Provides a complete experiment platform with
variant allocation, statistical analysis,
winner selection, and archiving.

Public API:
    - ExperimentManager: Unified entry point
    - Experiment: Experiment model
    - ExperimentResult: Analysis result
    - ExperimentStatus: Lifecycle status constants
    - Variant: Variant definition
    - VariantAllocator: Traffic allocation
    - VariantStats: Per-variant statistics
    - StatisticsCollector: Metrics collection
    - ExperimentAnalyzer: Statistical analysis
    - AnalysisResult: Analysis result details
    - WinnerSelector: Winner determination
    - WinnerResult: Winner selection result
    - ExperimentArchive: Experiment archiving
    - ExperimentValidator: Configuration validation
    - ExperimentMetrics: Prometheus metrics
    - ExperimentAudit: Audit logging
    - create_ab_variants: Create A/B variant pair
    - create_abc_variants: Create A/B/C variant set
"""

from __future__ import annotations

from .allocator import VariantAllocator
from .analyzer import AnalysisResult, ExperimentAnalyzer
from .archive import ExperimentArchive
from .audit import ExperimentAudit
from .experiment import Experiment, ExperimentResult, ExperimentStatus
from .manager import ExperimentManager
from .metrics import ExperimentMetrics
from .statistics import StatisticsCollector, VariantStats
from .validator import ExperimentValidator
from .variant import Variant, create_ab_variants, create_abc_variants
from .winner import WinnerResult, WinnerSelector

__all__ = [
    "ExperimentManager",
    "Experiment",
    "ExperimentResult",
    "ExperimentStatus",
    "Variant",
    "VariantAllocator",
    "VariantStats",
    "StatisticsCollector",
    "ExperimentAnalyzer",
    "AnalysisResult",
    "WinnerSelector",
    "WinnerResult",
    "ExperimentArchive",
    "ExperimentValidator",
    "ExperimentMetrics",
    "ExperimentAudit",
    "create_ab_variants",
    "create_abc_variants",
]

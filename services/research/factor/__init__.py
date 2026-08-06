"""Factor Research Engine — institutional alpha factor research, evaluation & alpha pool management.

Architecture::

    Dataset → Feature → Factor Pipeline → Evaluation → Alpha Pool → Report
"""

# ── Core Factor Engine ────────────────────────────────────────────────────
from .factor_engine import FactorEngine, FactorEngineState
from .factor_manager import FactorManager, FactorManagerState
from .factor_registry import FactorRegistry, FactorType
from .factor_repository import FactorRepository
from .factor_factory import FactorFactory
from .factor_pipeline import FactorPipeline, PipelineStage
from .factor_runtime import FactorRuntime, FactorRuntimeState
from .factor_context import FactorContext

# ── Feature Engineering ───────────────────────────────────────────────────
from .feature_engineering import (
    FeatureEngine,
    FeatureType,
    PriceFeature,
    VolumeFeature,
    VolatilityFeature,
    FundamentalFeature,
    AlternativeFeature,
    CustomFeature,
)
from .feature_store import FeatureStore, FeatureStoreState, FeatureRecord
from .feature_registry import FeatureRegistry, FeatureSchema
from .feature_selector import FeatureSelector, SelectionMethod
from .feature_validator import FeatureValidator, FeatureValidationReport
from .feature_cache import FeatureCache, FeatureCacheBackend, FeatureCacheEntry

# ── Factor Transformations ────────────────────────────────────────────────
from .normalization import Normalizer, NormalizationMethod
from .neutralization import Neutralizer, NeutralizationMethod
from .winsorization import Winsorizer, WinsorizationMethod
from .standardization import Standardizer
from .ranking import Ranker, RankingMethod
from .quantile import QuantileAnalyzer, QuantileMethod
from .orthogonalization import Orthogonalizer, OrthogonalizationMethod

# ── Factor Evaluation ─────────────────────────────────────────────────────
from .ic_analysis import ICAnalyzer, ICResult
from .rankic_analysis import RankICAnalyzer, RankICResult
from .icir_analysis import IciRAnalyzer, IciRResult
from .decay_analysis import DecayAnalyzer, DecayResult
from .turnover_analysis import TurnoverAnalyzer, TurnoverResult
from .exposure_analysis import ExposureAnalyzer, ExposureResult
from .correlation_analysis import CorrelationAnalyzer, CorrelationResult

# ── Alpha Pool & Report ───────────────────────────────────────────────────
from .alpha_pool import AlphaPool, AlphaState, AlphaEntry
from .factor_report import FactorReport, ReportSection as FactorReportSection

# ── Observability ─────────────────────────────────────────────────────────
from .metrics import FactorMetrics
from .telemetry import FactorTracer, FactorSpan, FactorSpanContext
from .diagnostics import FactorDiagnostics, FactorDiagnosticReport, FactorDiagnosticStatus
from .health import FactorHealthCheck

__all__ = [
    # Core Engine
    "FactorEngine",
    "FactorEngineState",
    "FactorManager",
    "FactorManagerState",
    "FactorRegistry",
    "FactorType",
    "FactorRepository",
    "FactorFactory",
    "FactorPipeline",
    "PipelineStage",
    "FactorRuntime",
    "FactorRuntimeState",
    "FactorContext",
    # Feature Engineering
    "FeatureEngine",
    "FeatureType",
    "PriceFeature",
    "VolumeFeature",
    "VolatilityFeature",
    "FundamentalFeature",
    "AlternativeFeature",
    "CustomFeature",
    "FeatureStore",
    "FeatureStoreState",
    "FeatureRecord",
    "FeatureRegistry",
    "FeatureSchema",
    "FeatureSelector",
    "SelectionMethod",
    "FeatureValidator",
    "FeatureValidationReport",
    "FeatureCache",
    "FeatureCacheBackend",
    "FeatureCacheEntry",
    # Transformations
    "Normalizer",
    "NormalizationMethod",
    "Neutralizer",
    "NeutralizationMethod",
    "Winsorizer",
    "WinsorizationMethod",
    "Standardizer",
    "Ranker",
    "RankingMethod",
    "QuantileAnalyzer",
    "QuantileMethod",
    "Orthogonalizer",
    "OrthogonalizationMethod",
    # Evaluation
    "ICAnalyzer",
    "ICResult",
    "RankICAnalyzer",
    "RankICResult",
    "IciRAnalyzer",
    "IciRResult",
    "DecayAnalyzer",
    "DecayResult",
    "TurnoverAnalyzer",
    "TurnoverResult",
    "ExposureAnalyzer",
    "ExposureResult",
    "CorrelationAnalyzer",
    "CorrelationResult",
    # Alpha Pool & Report
    "AlphaPool",
    "AlphaState",
    "AlphaEntry",
    "FactorReport",
    "FactorReportSection",
    # Observability
    "FactorMetrics",
    "FactorTracer",
    "FactorSpan",
    "FactorSpanContext",
    "FactorDiagnostics",
    "FactorDiagnosticReport",
    "FactorDiagnosticStatus",
    "FactorHealthCheck",
]

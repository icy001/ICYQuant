"""
ICYQuant Unified Market Data Normalization Engine.

Commit 16 Part 1.2 — Canonical market data model with enterprise-grade
validation, quality pipeline, and multi-asset-class normalizers.
"""

from .market_data_engine import MarketDataEngine, EngineState, EngineConfig
from .market_data_runtime import (
    MarketDataRuntime,
    MarketDataRuntimeStatus,
    MarketDataRuntimeConfig,
)
from .market_data_manager import MarketDataManager
from .market_data_controller import MarketDataController
from .canonical_model import (
    CanonicalMarketData,
    CanonicalTick,
    CanonicalTrade,
    CanonicalQuote,
    CanonicalOrderBook,
    CanonicalKLine,
    CanonicalOptionChain,
    CanonicalFutures,
    CanonicalFX,
    CanonicalCrypto,
    CanonicalIndex,
    AssetClass,
    DataQuality,
    MarketDataEventType,
)
from .market_data_pipeline import MarketDataPipeline, PipelineStage, PipelineConfig
from .market_data_normalizer import MarketDataNormalizer
from .tick_normalizer import TickNormalizer
from .trade_normalizer import TradeNormalizer
from .orderbook_normalizer import OrderBookNormalizer
from .kline_normalizer import KLineNormalizer
from .quote_normalizer import QuoteNormalizer
from .option_chain_normalizer import OptionChainNormalizer
from .futures_normalizer import FuturesNormalizer
from .fx_normalizer import FXNormalizer
from .crypto_normalizer import CryptoNormalizer
from .index_normalizer import IndexNormalizer
from .symbol_mapper import SymbolMapper, SymbolMapping, SymbolMappingRegistry
from .exchange_mapper import ExchangeMapper, ExchangeMapping
from .timestamp_normalizer import TimestampNormalizer
from .timezone_converter import TimezoneConverter, MarketTimezone
from .currency_normalizer import CurrencyNormalizer, CurrencyPair
from .corporate_action_processor import (
    CorporateActionProcessor,
    CorporateAction,
    CorporateActionType,
)
from .instrument_registry import (
    InstrumentRegistry,
    Instrument,
    InstrumentType,
    InstrumentStatus,
)
from .schema_registry import SchemaRegistry, SchemaDefinition, SchemaVersion
from .schema_validator import SchemaValidator, ValidationResult, ValidationSeverity
from .data_validator import DataValidator, DataValidationRule
from .quality_engine import QualityEngine, QualityReport, QualityDimension
from .duplicate_detector import DuplicateDetector
from .gap_detector import GapDetector, GapRecord
from .outlier_detector import OutlierDetector, OutlierRecord
from .market_data_cache import MarketDataCache, CacheEntry, CachePolicy
from .metrics import MarketDataMetrics
from .telemetry import (
    MarketDataTelemetry,
    NormalizationSpan,
    PipelineTrace,
)
from .diagnostics import MarketDataDiagnostics, DiagnosticResult, DiagnosticLevel
from .health import MarketDataHealthChecker, HealthStatus

__all__ = [
    # Engine
    "MarketDataEngine",
    "EngineState",
    "EngineConfig",
    "MarketDataRuntime",
    "MarketDataRuntimeStatus",
    "MarketDataRuntimeConfig",
    "MarketDataManager",
    "MarketDataController",
    # Canonical Model
    "CanonicalMarketData",
    "CanonicalTick",
    "CanonicalTrade",
    "CanonicalQuote",
    "CanonicalOrderBook",
    "CanonicalKLine",
    "CanonicalOptionChain",
    "CanonicalFutures",
    "CanonicalFX",
    "CanonicalCrypto",
    "CanonicalIndex",
    "AssetClass",
    "DataQuality",
    "MarketDataEventType",
    # Pipeline
    "MarketDataPipeline",
    "PipelineStage",
    "PipelineConfig",
    "MarketDataNormalizer",
    # Normalizers
    "TickNormalizer",
    "TradeNormalizer",
    "OrderBookNormalizer",
    "KLineNormalizer",
    "QuoteNormalizer",
    "OptionChainNormalizer",
    "FuturesNormalizer",
    "FXNormalizer",
    "CryptoNormalizer",
    "IndexNormalizer",
    # Mapping
    "SymbolMapper",
    "SymbolMapping",
    "SymbolMappingRegistry",
    "ExchangeMapper",
    "ExchangeMapping",
    "InstrumentRegistry",
    "Instrument",
    "InstrumentType",
    "InstrumentStatus",
    # Time & Currency
    "TimestampNormalizer",
    "TimezoneConverter",
    "MarketTimezone",
    "CurrencyNormalizer",
    "CurrencyPair",
    "CorporateActionProcessor",
    "CorporateAction",
    "CorporateActionType",
    # Schema & Validation
    "SchemaRegistry",
    "SchemaDefinition",
    "SchemaVersion",
    "SchemaValidator",
    "ValidationResult",
    "ValidationSeverity",
    "DataValidator",
    "DataValidationRule",
    "QualityEngine",
    "QualityReport",
    "QualityDimension",
    "DuplicateDetector",
    "GapDetector",
    "GapRecord",
    "OutlierDetector",
    "OutlierRecord",
    # Cache & Observability
    "MarketDataCache",
    "CacheEntry",
    "CachePolicy",
    "MarketDataMetrics",
    "MarketDataTelemetry",
    "NormalizationSpan",
    "PipelineTrace",
    "MarketDataDiagnostics",
    "DiagnosticResult",
    "DiagnosticLevel",
    "MarketDataHealthChecker",
    "HealthStatus",
]

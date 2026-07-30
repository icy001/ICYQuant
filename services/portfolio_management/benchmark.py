"""Benchmark Manager — benchmark definitions, tracking, and comparison."""

import time
import uuid
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    MARKET_INDEX = "market_index"
    PEER_GROUP = "peer_group"
    ABSOLUTE_RETURN = "absolute_return"
    CUSTOM_BASKET = "custom_basket"
    RISK_FREE = "risk_free"
    HYBRID = "hybrid"


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark management."""

    default_benchmark_id: str = ""
    tracking_error_limit: float = 0.05  # 5% max TE
    min_history_days: int = 252  # 1 year minimum
    enable_peer_comparison: bool = True
    peer_group_size: int = 20
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkFamily:
    """A family of related benchmarks (e.g., MSCI China, CSI series)."""

    family_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    provider: str = ""  # MSCI, FTSE, CSI, S&P, etc.
    region: str = "cn"
    asset_class: str = "equity"
    benchmarks: List[str] = field(default_factory=list)  # benchmark IDs
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Benchmark:
    """A benchmark definition."""

    benchmark_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    benchmark_type: BenchmarkType = BenchmarkType.MARKET_INDEX
    ticker: str = ""  # e.g., 000300.SH for CSI 300
    asset_class: str = "equity"
    currency: str = "CNY"
    family_id: str = ""
    description: str = ""
    is_default: bool = False
    weights: Dict[str, float] = field(default_factory=dict)
    historical_returns: List[float] = field(default_factory=list)
    annual_return: float = 0.0
    annual_volatility: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_return(self, ret: float) -> None:
        self.historical_returns.append(ret)
        self._recalculate_stats()

    def _recalculate_stats(self) -> None:
        if len(self.historical_returns) < 2:
            return
        mean = sum(self.historical_returns) / len(self.historical_returns)
        self.annual_return = mean * 252
        variance = sum((r - mean) ** 2 for r in self.historical_returns) / (len(self.historical_returns) - 1)
        self.annual_volatility = math.sqrt(variance * 252)

    @property
    def return_count(self) -> int:
        return len(self.historical_returns)


@dataclass
class TrackingError:
    """Tracking error between portfolio and benchmark."""

    portfolio_id: str = ""
    benchmark_id: str = ""
    tracking_error_annual: float = 0.0
    information_ratio: float = 0.0
    beta: float = 0.0
    alpha_annual: float = 0.0
    correlation: float = 0.0
    active_return: float = 0.0
    n_periods: int = 0
    calculated_at: float = field(default_factory=time.time)


class BenchmarkManager:
    """Manages benchmarks for portfolio comparison and performance measurement.

    Supports:
    - Market indices (CSI 300, S&P 500, etc.)
    - Peer group benchmarks
    - Custom composite benchmarks
    - Absolute return targets
    - Benchmark families
    - Tracking error calculation
    """

    def __init__(self, config: Optional[BenchmarkConfig] = None):
        self.config = config or BenchmarkConfig()
        self._benchmarks: Dict[str, Benchmark] = {}
        self._families: Dict[str, BenchmarkFamily] = {}
        self._tracking_errors: List[TrackingError] = []

    def register_benchmark(self, benchmark: Benchmark) -> Benchmark:
        if not benchmark.benchmark_id:
            benchmark.benchmark_id = str(uuid.uuid4())[:8]
        self._benchmarks[benchmark.benchmark_id] = benchmark
        if benchmark.is_default:
            self.config.default_benchmark_id = benchmark.benchmark_id

        # Link to family
        if benchmark.family_id and benchmark.family_id in self._families:
            family = self._families[benchmark.family_id]
            if benchmark.benchmark_id not in family.benchmarks:
                family.benchmarks.append(benchmark.benchmark_id)

        logger.info("Benchmark registered: %s (%s)", benchmark.name, benchmark.ticker)
        return benchmark

    def create_family(
        self, name: str, provider: str, region: str, asset_class: str
    ) -> BenchmarkFamily:
        family = BenchmarkFamily(
            name=name,
            provider=provider,
            region=region,
            asset_class=asset_class,
        )
        self._families[family.family_id] = family
        return family

    def get_benchmark(self, benchmark_id: str) -> Optional[Benchmark]:
        return self._benchmarks.get(benchmark_id)

    def get_default_benchmark(self) -> Optional[Benchmark]:
        return self._benchmarks.get(self.config.default_benchmark_id)

    def list_benchmarks(
        self,
        benchmark_type: Optional[BenchmarkType] = None,
        asset_class: Optional[str] = None,
    ) -> List[Benchmark]:
        results = list(self._benchmarks.values())
        if benchmark_type:
            results = [b for b in results if b.benchmark_type == benchmark_type]
        if asset_class:
            results = [b for b in results if b.asset_class == asset_class]
        return results

    def create_custom_benchmark(
        self,
        name: str,
        constituents: Dict[str, float],  # {ticker: weight}
        currency: str = "CNY",
    ) -> Benchmark:
        """Create a custom composite benchmark."""
        benchmark = Benchmark(
            name=name,
            benchmark_type=BenchmarkType.CUSTOM_BASKET,
            ticker="CUSTOM",
            currency=currency,
            weights=constituents,
        )
        return self.register_benchmark(benchmark)

    def calculate_tracking_error(
        self,
        portfolio_id: str,
        benchmark_id: str,
        portfolio_returns: List[float],
        benchmark_returns: Optional[List[float]] = None,
    ) -> TrackingError:
        """Calculate tracking error between portfolio and benchmark."""
        benchmark = self._benchmarks.get(benchmark_id)

        if benchmark_returns is None:
            benchmark_returns = benchmark.historical_returns if benchmark else []

        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 20:
            logger.warning("Insufficient data for tracking error: %d periods", n)
            return TrackingError(
                portfolio_id=portfolio_id,
                benchmark_id=benchmark_id,
                n_periods=n,
            )

        # Align to same length
        p_returns = portfolio_returns[-n:]
        b_returns = benchmark_returns[-n:]

        # Calculate metrics
        excess = [p - b for p, b in zip(p_returns, b_returns)]
        mean_excess = sum(excess) / n

        te_daily = math.sqrt(sum((e - mean_excess) ** 2 for e in excess) / (n - 1))
        te_annual = te_daily * math.sqrt(252)

        mean_p = sum(p_returns) / n
        mean_b = sum(b_returns) / n

        # Beta
        if n > 1:
            var_b = sum((r - mean_b) ** 2 for r in b_returns) / (n - 1)
            cov = sum(
                (p_returns[i] - mean_p) * (b_returns[i] - mean_b) for i in range(n)
            ) / (n - 1)
            beta = cov / var_b if var_b > 0 else 1.0
        else:
            beta = 1.0

        # Alpha (annualized)
        alpha_annual = (mean_p - beta * mean_b) * 252

        # Correlation
        if n > 1:
            std_p = math.sqrt(sum((r - mean_p) ** 2 for r in p_returns) / (n - 1))
            std_b = math.sqrt(sum((r - mean_b) ** 2 for r in b_returns) / (n - 1))
            correlation = cov / (std_p * std_b) if std_p > 0 and std_b > 0 else 0.0
        else:
            correlation = 0.0

        ir = (mean_excess * 252) / te_annual if te_annual > 0 else 0.0

        te = TrackingError(
            portfolio_id=portfolio_id,
            benchmark_id=benchmark_id,
            tracking_error_annual=te_annual,
            information_ratio=ir,
            beta=beta,
            alpha_annual=alpha_annual,
            correlation=correlation,
            active_return=mean_excess * 252,
            n_periods=n,
        )
        self._tracking_errors.append(te)
        return te

    def get_tracking_errors(
        self, portfolio_id: Optional[str] = None, limit: int = 50
    ) -> List[TrackingError]:
        results = self._tracking_errors
        if portfolio_id:
            results = [t for t in results if t.portfolio_id == portfolio_id]
        return results[-limit:]

    def compare_benchmarks(
        self, benchmark_ids: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Compare multiple benchmarks side by side."""
        comparison = {}
        for bid in benchmark_ids:
            b = self._benchmarks.get(bid)
            if b:
                comparison[b.name] = {
                    "annual_return": b.annual_return,
                    "annual_volatility": b.annual_volatility,
                    "sharpe_ratio": (
                        (b.annual_return - 0.03) / b.annual_volatility
                        if b.annual_volatility > 0 else 0.0
                    ),
                    "n_observations": b.return_count,
                    "type": b.benchmark_type.value,
                }
        return comparison

    def get_summary(self) -> Dict[str, Any]:
        benchmarks = list(self._benchmarks.values())
        by_type: Dict[str, int] = {}
        for b in benchmarks:
            t = b.benchmark_type.value
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_benchmarks": len(benchmarks),
            "total_families": len(self._families),
            "total_tracking_calculations": len(self._tracking_errors),
            "default_benchmark": self.config.default_benchmark_id,
            "benchmarks_by_type": by_type,
        }

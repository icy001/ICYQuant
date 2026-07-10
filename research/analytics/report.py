from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime

from .metrics import (
    calculate_total_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
)
from .benchmark import Benchmark, BenchmarkResult


@dataclass
class PerformanceReport:
    symbol: str
    strategy_name: str
    initial_capital: float
    final_equity: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    num_trades: int
    win_rate: float
    equity_curve: List[Tuple[datetime, float]]
    benchmark_result: Optional[BenchmarkResult] = None

    @classmethod
    def generate(
        cls,
        symbol: str,
        strategy_name: str,
        initial_capital: float,
        equity_curve: List[Tuple[datetime, float]],
        num_trades: int = 0,
        win_rate: float = 0.0,
        benchmark: Optional[Benchmark] = None,
    ) -> "PerformanceReport":
        final_equity = equity_curve[-1][1] if equity_curve else initial_capital
        
        total_return = calculate_total_return(initial_capital, final_equity)
        max_drawdown = calculate_max_drawdown(equity_curve)
        sharpe_ratio = calculate_sharpe_ratio(equity_curve)
        sortino_ratio = calculate_sortino_ratio(equity_curve)
        
        benchmark_result = None
        if benchmark:
            benchmark_result = benchmark.compare(equity_curve)
        
        return cls(
            symbol=symbol,
            strategy_name=strategy_name,
            initial_capital=initial_capital,
            final_equity=final_equity,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            num_trades=num_trades,
            win_rate=win_rate,
            equity_curve=equity_curve,
            benchmark_result=benchmark_result,
        )

    def __str__(self) -> str:
        lines = [
            "=" * 45,
            "ICYQuant Performance Report",
            "=" * 45,
            "",
            f"Symbol:",
            f"{self.symbol}",
            "",
            f"Strategy:",
            f"{self.strategy_name}",
            "",
            f"Initial Capital:",
            f"{self.initial_capital:,.0f} USD",
            "",
            f"Final Equity:",
            f"{self.final_equity:,.0f} USD",
            "",
            f"Total Return:",
            f"{self.total_return:.2%}",
            "",
            f"Sharpe Ratio:",
            f"{self.sharpe_ratio:.2f}",
            "",
            f"Sortino Ratio:",
            f"{self.sortino_ratio:.2f}",
            "",
            f"Maximum Drawdown:",
            f"{self.max_drawdown:.2%}",
            "",
            f"Number of Trades:",
            f"{self.num_trades}",
            "",
            f"Win Rate:",
            f"{self.win_rate:.1%}",
            "",
        ]
        
        if self.benchmark_result:
            lines.extend([
                f"Benchmark:",
                f"{self.benchmark_result.benchmark_return:.2%}",
                "",
                f"Alpha:",
                f"{self.benchmark_result.alpha:.2%}",
                "",
            ])
        
        lines.append("=" * 45)
        
        return "\n".join(lines)
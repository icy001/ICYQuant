import math
import statistics
from typing import List, Tuple
from datetime import datetime


def calculate_total_return(initial_capital: float, final_equity: float) -> float:
    if initial_capital == 0:
        return 0.0
    return (final_equity - initial_capital) / initial_capital


def calculate_returns(equities: List[float]) -> List[float]:
    returns = []
    for i in range(1, len(equities)):
        if equities[i-1] > 0:
            r = equities[i] / equities[i-1] - 1
            returns.append(r)
    return returns


def calculate_max_drawdown(equity_curve: List[Tuple[datetime, float]]) -> float:
    if not equity_curve:
        return 0.0
    
    peak = equity_curve[0][1]
    max_dd = 0.0
    
    for _, equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak
        if drawdown > max_dd:
            max_dd = drawdown
    
    return max_dd


def calculate_max_drawdown_from_equities(equities: List[float]) -> float:
    if not equities:
        return 0.0
    
    peak = equities[0]
    max_dd = 0.0
    
    for value in equities:
        if value > peak:
            peak = value
        dd = (value - peak) / peak
        max_dd = min(max_dd, dd)
    
    return abs(max_dd)


def calculate_newey_west_t(
    values: List[float],
    lag: int = 0,
    *,
    auto_lag: bool = False,
) -> float:
    """t-statistic of the mean using Newey-West HAC standard errors.

    Why this exists: the naive t = mean / (sd / sqrt(n)) assumes independent
    observations. Overlapping returns, rolling positions, or daily P&L held
    for days all violate that, and the naive t then overstates significance.
    In this repository the same HAC implementation was copied into four
    separate experiment scripts; it lives here now so there is one truth.

    ``lag`` is the number of autocovariance terms to include. Rule of thumb
    for overlapping horizons is lag >= hold - 1. With ``auto_lag=True`` the
    Newey-West (1994) plug-in bandwidth is used instead.

    Returns NaN when there are fewer than 10 observations or zero variance.
    """
    n = len(values)
    if n < 10:
        return float("nan")

    xs = [float(v) for v in values]
    mean = sum(xs) / n
    eps = [v - mean for v in xs]

    gamma0 = sum(e * e for e in eps) / n
    if gamma0 <= 0:
        return float("nan")

    if auto_lag:
        # Newey-West (1994): floor(4 * (n/100)^(2/9))
        lag = int(4 * (n / 100.0) ** (2.0 / 9.0))
    lag = max(0, min(int(lag), n - 1))

    variance = gamma0
    for k in range(1, lag + 1):
        gamma_k = sum(eps[k + i] * eps[i] for i in range(n - k)) / n
        weight = 1.0 - k / (lag + 1.0)          # Bartlett kernel
        variance += 2.0 * weight * gamma_k

    # A HAC variance can go non-positive with a badly chosen lag.
    if variance <= 0:
        return float("nan")

    se = math.sqrt(variance / n)
    return mean / se


def calculate_sharpe_ratio(equity_curve: List[Tuple[datetime, float]], risk_free_rate: float = 0.0, periods: int = 252) -> float:
    if len(equity_curve) < 2:
        return 0.0
    
    returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = equity_curve[i-1][1]
        curr_equity = equity_curve[i][1]
        if prev_equity > 0:
            returns.append((curr_equity - prev_equity) / prev_equity)
    
    if len(returns) < 2:
        return 0.0
    
    avg = statistics.mean(returns)
    vol = statistics.stdev(returns)
    
    if vol == 0:
        return 0.0
    
    return avg / vol * math.sqrt(periods)


def calculate_sortino_ratio(equity_curve: List[Tuple[datetime, float]], risk_free_rate: float = 0.0, periods: int = 252) -> float:
    if len(equity_curve) < 2:
        return 0.0
    
    returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = equity_curve[i-1][1]
        curr_equity = equity_curve[i][1]
        if prev_equity > 0:
            returns.append((curr_equity - prev_equity) / prev_equity)
    
    if not returns:
        return 0.0
    
    downside = [r for r in returns if r < 0]
    
    if len(downside) < 2:
        return 0.0
    
    avg_return = statistics.mean(returns)
    downside_std = statistics.stdev(downside)
    
    if downside_std == 0:
        return 0.0
    
    return avg_return / downside_std * math.sqrt(periods)
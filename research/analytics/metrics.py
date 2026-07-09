import numpy as np


def calculate_sharpe_ratio(returns, risk_free_rate: float = 0.02) -> float:
    if len(returns) < 2:
        return 0.0
    
    returns = np.array(returns)
    excess_returns = returns - risk_free_rate / 252
    
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns)
    
    if std_excess == 0:
        return 0.0
    
    return mean_excess / std_excess * np.sqrt(252)


def calculate_sortino_ratio(returns, risk_free_rate: float = 0.02) -> float:
    if len(returns) < 2:
        return 0.0
    
    returns = np.array(returns)
    excess_returns = returns - risk_free_rate / 252
    
    mean_excess = np.mean(excess_returns)
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return 0.0
    
    downside_std = np.std(downside_returns)
    
    if downside_std == 0:
        return 0.0
    
    return mean_excess / downside_std * np.sqrt(252)


def calculate_max_drawdown(equity_curve) -> float:
    if len(equity_curve) < 2:
        return 0.0
    
    equity_curve = np.array(equity_curve)
    peak = equity_curve[0]
    max_drawdown = 0.0
    
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    return max_drawdown


def calculate_calmar_ratio(returns, equity_curve) -> float:
    if len(returns) < 2:
        return 0.0
    
    total_return = np.prod(1 + np.array(returns)) - 1
    max_drawdown = calculate_max_drawdown(equity_curve)
    
    if max_drawdown == 0:
        return 0.0
    
    return total_return / max_drawdown


def calculate_win_rate(trades) -> float:
    if len(trades) == 0:
        return 0.0
    
    winning_trades = sum(1 for t in trades if t.cash_change > 0)
    return winning_trades / len(trades)


def calculate_profit_factor(trades) -> float:
    if len(trades) == 0:
        return 0.0
    
    gross_profit = sum(-t.cash_change for t in trades if t.side == "BUY" and t.cash_change < 0)
    gross_loss = sum(t.cash_change for t in trades if t.side == "BUY" and t.cash_change > 0)
    
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    
    return gross_profit / gross_loss


def calculate_avg_trade_return(trades) -> float:
    if len(trades) == 0:
        return 0.0
    
    total_pnl = sum(-t.cash_change if t.side == "BUY" else t.cash_change for t in trades)
    return total_pnl / len(trades)
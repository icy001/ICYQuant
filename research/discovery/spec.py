"""Strategy Discovery Specification v1 — the sealed contract of Discovery Lab v1.

This module is the single source of truth for the first discovery experiment:

    - the five strategy families and the concrete rule structures,
    - the bounded parameter grids (no unbounded / random search),
    - the Train / Validation / OOS split (adapted to the current 3y dataset),
    - the per-asset transaction cost model,
    - the Discovery Gate v1 thresholds (fixed once; never tuned to make a
      candidate pass),
    - the multi-factor ranking weights.

Hard rule — *OOS data never participates in parameter selection*. The split
boundaries below are sealed here and consumed by the engine; no other module
may move them.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- #
# 1. Strategy families                                                         #
# --------------------------------------------------------------------------- #
FAMILY_NAMES = ("Trend", "Momentum", "Breakout", "Mean Reversion", "Hybrid")

# --------------------------------------------------------------------------- #
# 2. Concrete rule structures                                                  #
#    Each structure knows how to translate its parameters into an entry/exit   #
#    state machine. The generator only instantiates structures from the fixed  #
#    parameter grids below — the machine never writes arbitrary Python.        #
# --------------------------------------------------------------------------- #
STRUCTURES: dict[str, dict[str, Any]] = {
    # ---- Trend ------------------------------------------------------------- #
    "trend_ema_cross": {
        "family": "Trend",
        "description": "Long when EMA(fast) > EMA(slow); exit when EMA(fast) < EMA(slow).",
        "entry": "EMA(fast) > EMA(slow)",
        "exit": "EMA(fast) < EMA(slow)",
        "params": {"fast": "int", "slow": "int"},
    },
    "trend_sma_cross": {
        "family": "Trend",
        "description": "Long when SMA(fast) > SMA(slow); exit when SMA(fast) < SMA(slow).",
        "entry": "SMA(fast) > SMA(slow)",
        "exit": "SMA(fast) < SMA(slow)",
        "params": {"fast": "int", "slow": "int"},
    },
    "trend_ema_supertrend": {
        "family": "Trend",
        "description": "Long when EMA(fast) > EMA(slow) AND Supertrend is bullish; "
                       "exit when EMA(fast) < EMA(slow) OR Supertrend turns bearish.",
        "entry": "EMA(fast) > EMA(slow) AND Supertrend(atr_period, mult) = Bullish",
        "exit": "EMA(fast) < EMA(slow) OR Supertrend = Bearish",
        "params": {"fast": "int", "slow": "int", "atr_period": "int", "mult": "float"},
    },
    "trend_ema_adx": {
        "family": "Trend",
        "description": "Long when EMA(fast) > EMA(slow) AND ADX(period) > threshold; "
                       "exit when EMA(fast) < EMA(slow) OR ADX < exit_threshold.",
        "entry": "EMA(fast) > EMA(slow) AND ADX > entry_adx",
        "exit": "EMA(fast) < EMA(slow) OR ADX < exit_adx",
        "params": {"fast": "int", "slow": "int", "adx_period": "int",
                   "entry_adx": "float", "exit_adx": "float"},
    },
    "trend_donchian": {
        "family": "Trend",
        "description": "Long when close > Donchian upper; exit when close < Donchian middle.",
        "entry": "Close > Donchian(period).Upper",
        "exit": "Close < Donchian(period).Middle",
        "params": {"period": "int"},
    },
    # ---- Momentum ---------------------------------------------------------- #
    "momentum_rsi": {
        "family": "Momentum",
        "description": "Long when RSI crosses above oversold level; "
                       "exit when RSI crosses below overbought level.",
        "entry": "RSI crosses up through oversold",
        "exit": "RSI crosses down through overbought",
        "params": {"period": "int", "oversold": "float", "overbought": "float"},
    },
    "momentum_roc": {
        "family": "Momentum",
        "description": "Long when ROC crosses above zero; exit when ROC crosses below zero.",
        "entry": "ROC(period) crosses up through 0",
        "exit": "ROC(period) crosses down through 0",
        "params": {"period": "int"},
    },
    "momentum_mom": {
        "family": "Momentum",
        "description": "Long when price momentum crosses above zero; exit below zero.",
        "entry": "Momentum(period) crosses up through 0",
        "exit": "Momentum(period) crosses down through 0",
        "params": {"period": "int"},
    },
    "momentum_macd": {
        "family": "Momentum",
        "description": "Long when MACD line crosses above its signal; exit below.",
        "entry": "MACD(fast, slow, signal) crosses up through signal",
        "exit": "MACD crosses down through signal",
        "params": {"fast": "int", "slow": "int", "signal": "int"},
    },
    "momentum_stochastic": {
        "family": "Momentum",
        "description": "Long when %K turns up from below oversold; exit when %K turns down from overbought.",
        "entry": "%K crosses up through oversold",
        "exit": "%K crosses down through overbought",
        "params": {"period": "int", "oversold": "float", "overbought": "float"},
    },
    # ---- Breakout ---------------------------------------------------------- #
    "breakout_donchian": {
        "family": "Breakout",
        "description": "Long when close breaks the Donchian upper; exit on Donchian middle.",
        "entry": "Close > Donchian(period).Upper",
        "exit": "Close < Donchian(period).Middle",
        "params": {"period": "int"},
    },
    "breakout_highlow": {
        "family": "Breakout",
        "description": "Long when close breaks the N-bar high; exit below the N-bar low.",
        "entry": "Close > rolling_high(period)",
        "exit": "Close < rolling_low(period)",
        "params": {"period": "int"},
    },
    "breakout_atr": {
        "family": "Breakout",
        "description": "Long when close > close[n] + k * ATR; exit when close < close[n] - k * ATR.",
        "entry": "Close > Close[lookback] + k * ATR(period)",
        "exit": "Close < Close[lookback] - k * ATR(period)",
        "params": {"period": "int", "lookback": "int", "k": "float"},
    },
    # ---- Mean Reversion ---------------------------------------------------- #
    "meanrev_bollinger": {
        "family": "Mean Reversion",
        "description": "Long when close < lower Bollinger band; exit when close > middle band.",
        "entry": "Close < BB(period, k).Lower",
        "exit": "Close > BB(period, k).Middle",
        "params": {"period": "int", "k": "float"},
    },
    "meanrev_rsi": {
        "family": "Mean Reversion",
        "description": "Long when RSI < oversold; exit when RSI recovers above mid level.",
        "entry": "RSI(period) < oversold",
        "exit": "RSI(period) > mid",
        "params": {"period": "int", "oversold": "float", "mid": "float"},
    },
    "meanrev_ma": {
        "family": "Mean Reversion",
        "description": "Long when close falls far below SMA(entry); exit when close recovers above SMA(exit).",
        "entry": "Close < SMA(entry_period) * (1 - pct)",
        "exit": "Close > SMA(exit_period)",
        "params": {"entry_period": "int", "exit_period": "int", "pct": "float"},
    },
    # ---- Hybrid ------------------------------------------------------------ #
    "hybrid_ema_rsi": {
        "family": "Hybrid",
        "description": "Trend with momentum filter: long when EMA(fast) > EMA(slow) AND RSI > 50; "
                       "exit when EMA(fast) < EMA(slow) OR RSI < exit_level.",
        "entry": "EMA(fast) > EMA(slow) AND RSI(period) > 50",
        "exit": "EMA(fast) < EMA(slow) OR RSI(period) < exit_level",
        "params": {"fast": "int", "slow": "int", "rsi_period": "int", "exit_level": "float"},
    },
    "hybrid_ema_adx": {
        "family": "Hybrid",
        "description": "Trend with trend-strength filter: long when EMA(fast) > EMA(slow) AND ADX > 25; "
                       "exit when EMA(fast) < EMA(slow) OR ADX < 20.",
        "entry": "EMA(fast) > EMA(slow) AND ADX(adx_period) > 25",
        "exit": "EMA(fast) < EMA(slow) OR ADX(adx_period) < 20",
        "params": {"fast": "int", "slow": "int", "adx_period": "int"},
    },
    "hybrid_breakout_atr": {
        "family": "Hybrid",
        "description": "Breakout with volatility filter: long when close > Donchian upper AND "
                       "ATR-normalised move > k; exit on Donchian middle.",
        "entry": "Close > Donchian(period).Upper AND ATR(period) > k * SMA(ATR, 50)",
        "exit": "Close < Donchian(period).Middle",
        "params": {"period": "int", "k": "float"},
    },
}

# --------------------------------------------------------------------------- #
# 3. Bounded parameter grids                                                   #
#    The generator enumerates exactly these combinations. No free-form random   #
#    search: every parameter value is whitelisted here (reproducibility).       #
# --------------------------------------------------------------------------- #
PARAMETER_SPACES: dict[str, list[dict[str, Any]]] = {
    "trend_ema_cross": [
        {"fast": f, "slow": s}
        for f in (5, 10, 15, 20, 25)
        for s in (30, 40, 50, 60, 80, 100)
        if s > f
    ],
    "trend_sma_cross": [
        {"fast": f, "slow": s}
        for f in (5, 10, 15, 20, 25)
        for s in (30, 40, 50, 60, 80, 100)
        if s > f
    ],
    "trend_ema_supertrend": [
        {"fast": f, "slow": s, "atr_period": ap, "mult": m}
        for (f, s) in ((10, 30), (10, 50), (20, 50), (20, 60), (25, 100))
        for ap in (5, 7, 10)
        for m in (2, 3, 4, 5)
    ],
    "trend_ema_adx": [
        {"fast": f, "slow": s, "adx_period": ap, "entry_adx": e, "exit_adx": e - 5}
        for (f, s) in ((10, 50), (20, 60), (20, 80))
        for ap in (7, 14, 21)
        for e in (20.0, 25.0, 30.0)
    ],
    "trend_donchian": [{"period": p} for p in (20, 30, 50, 80, 120)],
    # Momentum grids are sized so the pool >= the family target (60). The
    # generator deterministically samples the target count per family.
    "momentum_rsi": [
        {"period": p, "oversold": os, "overbought": ob}
        for p in (5, 7, 9, 14, 21)
        for (os, ob) in ((20.0, 80.0), (25.0, 75.0), (30.0, 70.0))
    ],
    "momentum_roc": [{"period": p} for p in (5, 10, 15, 20, 30, 40, 60)],
    "momentum_mom": [{"period": p} for p in (5, 10, 15, 20, 30, 40, 60)],
    "momentum_macd": [
        {"fast": f, "slow": s, "signal": sig}
        for (f, s, sig) in (
            (5, 21, 5), (8, 21, 5), (9, 21, 5), (12, 26, 9),
            (16, 48, 9), (20, 60, 9), (26, 52, 9), (12, 26, 5),
            (15, 30, 9), (18, 45, 9), (24, 52, 9), (30, 60, 9),
            (35, 70, 9), (40, 80, 9), (45, 90, 9), (60, 120, 9),
        )
    ],
    "momentum_stochastic": [
        {"period": p, "oversold": os, "overbought": ob}
        for p in (5, 7, 9, 14, 21)
        for (os, ob) in ((20.0, 80.0), (25.0, 75.0), (30.0, 70.0))
    ],
    "breakout_donchian": [{"period": p} for p in (10, 20, 30, 50, 80, 120)],
    "breakout_highlow": [{"period": p} for p in (10, 20, 30, 50, 80, 120)],
    "breakout_atr": [
        {"period": p, "lookback": lb, "k": k}
        for p in (7, 10, 14, 20)
        for lb in (10, 20, 30, 50)
        for k in (1.0, 1.5, 2.0, 3.0)
    ],
    "meanrev_bollinger": [
        {"period": p, "k": k}
        for p in (20, 30, 50, 80)
        for k in (1.5, 2.0, 2.5, 3.0, 3.5)
    ],
    "meanrev_rsi": [
        {"period": p, "oversold": os, "mid": mid}
        for p in (7, 9, 14, 21)
        for (os, mid) in ((20.0, 50.0), (25.0, 50.0), (30.0, 55.0))
    ],
    "meanrev_ma": [
        {"entry_period": e, "exit_period": x, "pct": pct}
        for (e, x) in ((20, 5), (50, 10), (100, 20), (200, 50),
                       (20, 10), (50, 20), (100, 50))
        for pct in (0.02, 0.03, 0.05)
    ],
    "hybrid_ema_rsi": [
        {"fast": f, "slow": s, "rsi_period": rp, "exit_level": ex}
        for (f, s) in ((10, 30), (10, 50), (20, 60), (20, 100))
        for rp in (7, 14)
        for ex in (40.0, 45.0, 50.0)
    ],
    "hybrid_ema_adx": [
        {"fast": f, "slow": s, "adx_period": ap}
        for (f, s) in ((10, 30), (10, 50), (20, 60), (20, 100))
        for ap in (7, 14, 21)
    ],
    "hybrid_breakout_atr": [
        {"period": p, "k": k}
        for p in (20, 50)
        for k in (1.0, 1.5, 2.0)
    ],
}

# --------------------------------------------------------------------------- #
# 4. Train / Validation / OOS split                                            #
#    The Research Universe v1.1 dataset spans 2023-01-02 -> 2025-12-31 (3y).   #
#    The user's *ideal* split (2021-2023 / 2024 / 2025-2026) requires 6y of    #
#    history; per the v1 rule "do not extend data now", v1 adapts the same     #
#    60/20/20 shape to the available range. When the dataset grows to >=6y,    #
#    switch SPLIT_CONFIG below to the ideal split (kept as IDEAL_SPLIT).       #
# --------------------------------------------------------------------------- #
SPLIT_CONFIG: dict[str, dict[str, str]] = {
    "name": "v1-3y-60-20-20",
    "train": {"start": "2023-01-01", "end": "2024-06-30"},
    "validation": {"start": "2024-07-01", "end": "2024-12-31"},
    "oos": {"start": "2025-01-01", "end": "2025-12-31"},
    "note": "Adapted from the ideal 2021-2023/2024/2025-2026 split to the "
            "current 3-year dataset (no data extension in v1).",
}

IDEAL_SPLIT: dict[str, dict[str, str]] = {
    "name": "ideal-6y",
    "train": {"start": "2021-01-01", "end": "2023-12-31"},
    "validation": {"start": "2024-01-01", "end": "2024-12-31"},
    "oos": {"start": "2025-01-01", "end": "2026-12-31"},
    "note": "User-specified split; requires >= 6y of data.",
}

# --------------------------------------------------------------------------- #
# 5. Per-asset transaction cost model                                          #
#    One-way cost in basis points (bps) per unit of notional traded. The       #
#    cost model combines commission + spread + slippage into a single per-     #
#    side number so a trade (entry + exit) pays 2x this rate. Assets with      #
#    higher turnover (A-shares, HK) and wider spreads (gold, silver) are       #
#    charged more so Discovery cannot systematically favour high-turnover      #
#    strategies on cheap-to-trade assets. Values are documented assumptions.   #
# --------------------------------------------------------------------------- #
COST_CONFIG: dict[str, dict[str, float]] = {
    "NVDA": {"commission_bps": 0.0, "spread_bps": 2.0, "slippage_bps": 3.0},
    "SPY": {"commission_bps": 0.0, "spread_bps": 1.0, "slippage_bps": 2.0},
    "QQQ": {"commission_bps": 0.0, "spread_bps": 1.0, "slippage_bps": 2.0},
    "000688.SH": {"commission_bps": 3.0, "spread_bps": 2.0, "slippage_bps": 3.0},
    "HSTECH": {"commission_bps": 2.0, "spread_bps": 3.0, "slippage_bps": 4.0},
    "EURUSD": {"commission_bps": 0.0, "spread_bps": 1.0, "slippage_bps": 0.5},
    "XAUUSD": {"commission_bps": 0.5, "spread_bps": 3.0, "slippage_bps": 2.5},
    "AU": {"commission_bps": 1.0, "spread_bps": 2.0, "slippage_bps": 3.0},
    "AG": {"commission_bps": 1.0, "spread_bps": 3.0, "slippage_bps": 4.0},
}

# --------------------------------------------------------------------------- #
# 6. Discovery Gate v1 thresholds                                              #
#    Sealed once; the engine never tunes these to let a candidate pass.        #
# --------------------------------------------------------------------------- #
GATE_THRESHOLDS: dict[str, Any] = {
    # minimum trades per asset segment (a candidate with fewer trades is noise)
    "min_trades": 20,
    # minimum annualised Sharpe required on Train / Validation / OOS
    "min_sharpe": 0.8,
    # OOS also has to be net positive (no return rescue — hard requirement)
    "min_oos_return": 0.0,
    # maximum drawdown (peak-to-trough, negative) allowed on OOS
    "max_drawdown": -0.30,
    # minimum profit factor (gross profit / gross loss) on OOS
    "min_profit_factor": 1.15,
    # walk-forward: fraction of in-sample rolling windows that must be positive
    "wf_min_positive_windows": 0.66,
    # parameter stability: min fraction of same-structure candidates with a
    # positive OOS Sharpe, and max coefficient of variation tolerated
    "stability_min_positive_frac": 0.50,
    "stability_max_cv": 1.5,
    # candidate-level: assets that must pass for the candidate to advance
    "min_assets_passed": 3,
    # complexity penalty basis (number of indicators + parameters)
    "complexity_base": 4,
}

# --------------------------------------------------------------------------- #
# 7. Multi-factor ranking score (user-specified weights)                       #
#    Score = 0.25*OOS Sharpe + 0.20*OOS Return + 0.15*Drawdown + 0.15*PF      #
#            + 0.10*Stability + 0.10*Trade Count - 0.05*Complexity            #
#    Each component is rank-normalised across the surviving candidates so      #
#    units (Sharpe vs return vs PF) are comparable.                            #
# --------------------------------------------------------------------------- #
SCORE_WEIGHTS: dict[str, float] = {
    "oos_sharpe": 0.25,
    "oos_return": 0.20,
    "drawdown": 0.15,
    "profit_factor": 0.15,
    "stability": 0.10,
    "trade_count": 0.10,
    "complexity": -0.05,
}


from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoverySpec:
    """The sealed v1 specification (single object mirroring this module)."""

    version: str = "v1"
    name: str = "Strategy Discovery Lab v1"
    universe: tuple[str, ...] = (
        "NVDA", "SPY", "QQQ", "000688.SH", "HSTECH",
        "EURUSD", "XAUUSD", "AU", "AG",
    )
    timeframe: str = "1H"
    candidates_total: int = 300
    family_target: dict[str, int] = field(default_factory=lambda: {
        "Trend": 100, "Momentum": 60, "Breakout": 60,
        "Mean Reversion": 50, "Hybrid": 30,
    })
    split: dict[str, dict[str, str]] = field(default_factory=lambda: SPLIT_CONFIG)
    structures: dict[str, dict[str, Any]] = field(default_factory=lambda: STRUCTURES)
    parameter_spaces: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: PARAMETER_SPACES)
    cost_config: dict[str, dict[str, float]] = field(default_factory=lambda: COST_CONFIG)
    gate_thresholds: dict[str, Any] = field(default_factory=lambda: GATE_THRESHOLDS)
    score_weights: dict[str, float] = field(default_factory=lambda: SCORE_WEIGHTS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "universe": list(self.universe),
            "timeframe": self.timeframe,
            "candidates_total": self.candidates_total,
            "family_target": dict(self.family_target),
            "split": self.split,
            "structures": {k: {"family": v["family"],
                               "entry": v["entry"], "exit": v["exit"]}
                           for k, v in self.structures.items()},
            "cost_config": self.cost_config,
            "gate_thresholds": self.gate_thresholds,
            "score_weights": self.score_weights,
        }


# Sealed v1 spec instance consumed across the Discovery Lab.
DISCOVERY_SPEC_V1 = DiscoverySpec()

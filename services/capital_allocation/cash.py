from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CashTier(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    RESERVE = "RESERVE"
    EMERGENCY = "EMERGENCY"
    DEPLOYABLE = "DEPLOYABLE"


class CashYieldStrategy(str, Enum):
    MAX_YIELD = "MAX_YIELD"
    MAX_LIQUIDITY = "MAX_LIQUIDITY"
    BALANCED = "BALANCED"


@dataclass
class CashReserve:
    tier: CashTier
    amount: float
    percentage: float
    yield_rate: float = 0.0
    instruments: List[str] = field(default_factory=list)


@dataclass
class CashPosition:
    total_cash: float
    total_aum: float
    cash_ratio: float
    reserves: List[CashReserve]
    deployable: float
    idle_threshold: float = 0.05
    emergency_ratio: float = 0.02


class CashManagementAI:
    """Cash Management AI - autonomously manages cash reserves and idle capital."""

    def __init__(self):
        self.positions: List[CashPosition] = []
        self.cash_count = 0

    def manage(self, cash):
        """Manage cash position and generate cash allocation plan.

        Args:
            cash: Cash data (str, float, dict, or CashPosition).

        Returns:
            Dict containing cash management plan.
        """
        if isinstance(cash, CashPosition):
            return self._process_position(cash)
        if isinstance(cash, dict):
            return self._manage_dict(cash)
        if isinstance(cash, (int, float)):
            return {"cash": cash}
        return {"cash": cash}

    def _process_position(self, position: CashPosition) -> dict:
        self.positions.append(position)
        return self._to_dict(position)

    def _manage_dict(self, data: dict) -> dict:
        self.cash_count += 1

        total_cash = data.get("total_cash", data.get("cash", 100000.0))
        total_aum = data.get("total_aum", data.get("aum", 1000000.0))
        market_regime = data.get("market_regime", "NORMAL")
        volatility = data.get("volatility", 0.15)
        conviction = data.get("conviction", 50)

        cash_ratio = total_cash / total_aum if total_aum > 0 else 1.0

        # Determine reserve allocations
        reserves = self._allocate_reserves(total_cash, cash_ratio, market_regime, volatility, conviction)

        # Calculate deployable
        emergency = next((r for r in reserves if r.tier == CashTier.EMERGENCY), None)
        reserve = next((r for r in reserves if r.tier == CashTier.RESERVE), None)
        operational = next((r for r in reserves if r.tier == CashTier.OPERATIONAL), None)

        locked = (emergency.amount if emergency else 0) + (reserve.amount if reserve else 0)
        deployable = total_cash - locked

        position = CashPosition(
            total_cash=round(total_cash, 2),
            total_aum=round(total_aum, 2),
            cash_ratio=round(cash_ratio, 4),
            reserves=reserves,
            deployable=round(deployable, 2),
            idle_threshold=self._calc_idle_threshold(market_regime, conviction),
            emergency_ratio=self._calc_emergency_ratio(market_regime, volatility),
        )
        self.positions.append(position)
        return self._to_dict(position)

    def _allocate_reserves(
        self, cash: float, cash_ratio: float, regime: str, vol: float, conviction: float
    ) -> List[CashReserve]:
        reserves = []

        # Emergency reserve (always protected)
        emergency_pct = self._calc_emergency_ratio(regime, vol)
        emergency_amt = cash * emergency_pct
        reserves.append(CashReserve(
            tier=CashTier.EMERGENCY,
            amount=round(emergency_amt, 2),
            percentage=round(emergency_pct * 100, 1),
            yield_rate=0.03,
            instruments=["T-Bills", "Money Market", "Overnight Reverse Repo"],
        ))

        # Strategic reserve
        reserve_pct = 0.10
        if regime.upper() in ("BEAR", "CRISIS", "HIGH_VOL"):
            reserve_pct = 0.20
        elif conviction >= 70:
            reserve_pct = 0.05
        reserve_amt = cash * reserve_pct
        reserves.append(CashReserve(
            tier=CashTier.RESERVE,
            amount=round(reserve_amt, 2),
            percentage=round(reserve_pct * 100, 1),
            yield_rate=0.04,
            instruments=["Short-term Bonds", "High-grade Commercial Paper"],
        ))

        # Operational cash
        operational_amt = cash * 0.03
        reserves.append(CashReserve(
            tier=CashTier.OPERATIONAL,
            amount=round(operational_amt, 2),
            percentage=3.0,
            yield_rate=0.01,
            instruments=["Cash Sweep", "Checking"],
        ))

        # Deployable cash
        used = emergency_pct + reserve_pct + 0.03
        deployable_pct = max(0.0, 1.0 - used)
        deployable_amt = cash * deployable_pct
        reserves.append(CashReserve(
            tier=CashTier.DEPLOYABLE,
            amount=round(deployable_amt, 2),
            percentage=round(deployable_pct * 100, 1),
            yield_rate=0.0,
            instruments=["Available for deployment"],
        ))

        return reserves

    def _calc_emergency_ratio(self, regime: str, vol: float) -> float:
        base = 0.02
        if regime.upper() in ("CRISIS",):
            base = 0.15
        elif regime.upper() in ("BEAR", "HIGH_VOL"):
            base = 0.08
        elif regime.upper() == "BEARISH":
            base = 0.05
        if vol > 0.30:
            base += 0.05
        elif vol > 0.20:
            base += 0.02
        return min(0.20, base)

    def _calc_idle_threshold(self, regime: str, conviction: float) -> float:
        base = 0.05
        if conviction >= 70:
            base = 0.02
        if regime.upper() in ("CRISIS", "BEAR"):
            base = 0.10
        return base

    def _to_dict(self, position: CashPosition) -> dict:
        return {
            "cash": {
                "total_cash": position.total_cash,
                "total_aum": position.total_aum,
                "cash_ratio": position.cash_ratio,
                "reserves": [
                    {
                        "tier": r.tier.value,
                        "amount": r.amount,
                        "percentage": r.percentage,
                        "yield_rate": r.yield_rate,
                        "instruments": r.instruments,
                    }
                    for r in position.reserves
                ],
                "deployable": position.deployable,
                "idle_threshold": position.idle_threshold,
                "emergency_ratio": position.emergency_ratio,
                "warning": "Excess idle cash - deploy capital" if position.cash_ratio > position.idle_threshold else None,
            }
        }

    def get_position(self) -> Optional[CashPosition]:
        """Get the latest cash position."""
        return self.positions[-1] if self.positions else None

    def get_deployable_cash(self) -> float:
        """Get currently deployable cash."""
        pos = self.get_position()
        return pos.deployable if pos else 0.0

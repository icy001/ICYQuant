from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MacroBias(str, Enum):
    STRONGLY_BULLISH = "STRONGLY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONGLY_BEARISH = "STRONGLY_BEARISH"


class CentralBankStance(str, Enum):
    DOVISH = "DOVISH"
    NEUTRAL = "NEUTRAL"
    HAWKISH = "HAWKISH"
    UNKNOWN = "UNKNOWN"


@dataclass
class MacroData:
    interest_rate: float
    inflation_rate: float
    gdp_growth: float
    unemployment_rate: float
    central_bank_stance: CentralBankStance
    money_supply_growth: float
    yield_curve_spread: float  # 10Y - 2Y
    credit_spread: float
    dollar_index: float
    timestamp: str = ""


@dataclass
class MacroView:
    bias: MacroBias
    confidence: float
    key_factors: List[str]
    risks: List[str]
    opportunities: List[str]
    asset_allocation_tilt: Dict[str, float] = field(default_factory=dict)


class MacroIntelligenceAgent:
    """Macro Intelligence Agent - analyzes macroeconomic conditions."""

    def __init__(self):
        self.last_view: Optional[MacroView] = None

    def analyze(self, macro_data):
        """Analyze macroeconomic data and generate a macro view.

        Args:
            macro_data: Macro data - can be MacroData dataclass or dict/symbol.

        Returns:
            Dict containing macro analysis result.
        """
        if isinstance(macro_data, MacroData):
            return self._analyze_macro(macro_data)
        return {"macro": macro_data}

    def _analyze_macro(self, data: MacroData) -> dict:
        bias = self._determine_bias(data)
        confidence = self._calculate_confidence(data)
        key_factors = self._identify_key_factors(data)
        risks = self._identify_risks(data)
        opportunities = self._identify_opportunities(data)

        return {
            "macro": {
                "bias": bias.value,
                "confidence": round(confidence, 2),
                "interest_rate": data.interest_rate,
                "inflation_rate": data.inflation_rate,
                "gdp_growth": data.gdp_growth,
                "unemployment_rate": data.unemployment_rate,
                "central_bank_stance": data.central_bank_stance.value,
                "yield_curve_spread": data.yield_curve_spread,
                "key_factors": key_factors,
                "risks": risks,
                "opportunities": opportunities,
            }
        }

    def _determine_bias(self, data: MacroData) -> MacroBias:
        score = 0

        # GDP growth
        if data.gdp_growth > 0.03:
            score += 2
        elif data.gdp_growth > 0:
            score += 1
        else:
            score -= 2

        # Inflation
        if 0.02 <= data.inflation_rate <= 0.03:
            score += 1
        elif data.inflation_rate > 0.05:
            score -= 2

        # Yield curve
        if data.yield_curve_spread > 0.01:
            score += 1
        elif data.yield_curve_spread < -0.005:
            score -= 2

        # Central bank
        if data.central_bank_stance == CentralBankStance.DOVISH:
            score += 1
        elif data.central_bank_stance == CentralBankStance.HAWKISH:
            score -= 1

        if score >= 3:
            return MacroBias.STRONGLY_BULLISH
        elif score >= 1:
            return MacroBias.BULLISH
        elif score <= -3:
            return MacroBias.STRONGLY_BEARISH
        elif score <= -1:
            return MacroBias.BEARISH
        return MacroBias.NEUTRAL

    def _calculate_confidence(self, data: MacroData) -> float:
        base = 0.5
        if data.central_bank_stance != CentralBankStance.UNKNOWN:
            base += 0.15
        if abs(data.gdp_growth) > 0.02:
            base += 0.10
        if data.inflation_rate > 0:
            base += 0.10
        if data.yield_curve_spread != 0:
            base += 0.15
        return min(1.0, base)

    def _identify_key_factors(self, data: MacroData) -> List[str]:
        factors = []
        if data.gdp_growth > 0.03:
            factors.append("Strong GDP growth supports risk assets")
        elif data.gdp_growth < 0:
            factors.append("Contracting GDP signals recession risk")

        if data.inflation_rate > 0.04:
            factors.append("Elevated inflation pressures central bank action")
        elif data.inflation_rate < 0.01:
            factors.append("Low inflation provides policy flexibility")

        if data.yield_curve_spread < 0:
            factors.append("Inverted yield curve warns of recession")
        elif data.yield_curve_spread > 0.02:
            factors.append("Steep yield curve supports economic expansion")

        if data.central_bank_stance == CentralBankStance.DOVISH:
            factors.append("Dovish central bank supports risk assets")
        elif data.central_bank_stance == CentralBankStance.HAWKISH:
            factors.append("Hawkish central bank pressures valuations")

        if not factors:
            factors.append("Mixed macro signals - neutral outlook")
        return factors

    def _identify_risks(self, data: MacroData) -> List[str]:
        risks = []
        if data.inflation_rate > 0.05:
            risks.append("Persistent inflation above target")
        if data.yield_curve_spread < -0.005:
            risks.append("Yield curve inversion - recession signal")
        if data.credit_spread > 0.03:
            risks.append("Widening credit spreads indicate stress")
        if data.unemployment_rate > 0.06:
            risks.append("Rising unemployment")
        if not risks:
            risks.append("No significant macro risks identified")
        return risks

    def _identify_opportunities(self, data: MacroData) -> List[str]:
        opportunities = []
        if data.gdp_growth > 0.02 and data.inflation_rate < 0.03:
            opportunities.append("Goldilocks environment favors equities")
        if data.central_bank_stance == CentralBankStance.DOVISH:
            opportunities.append("Rate-sensitive sectors benefit from dovish policy")
        if data.yield_curve_spread > 0.015:
            opportunities.append("Steep curve favors financial sector")
        if not opportunities:
            opportunities.append("Monitor for emerging macro opportunities")
        return opportunities

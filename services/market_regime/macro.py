"""Macro Environment Analyzer – analyze macroeconomic conditions."""

from typing import Any, Dict, List, Optional


class MacroAnalyzer:
    """Analyzes macroeconomic environment for regime classification.

    Analyzes:
    - Interest rate environment (rate level, direction, yield curve)
    - Inflation conditions
    - USD strength
    - Central bank policy stance
    - Credit conditions

    Outputs a macro regime signal that feeds into the overall regime classifier.
    """

    # Macro environment types
    GROWTH_INFLATION = "GROWTH_INFLATION"  # expansion with inflation
    GOLDILOCKS = "GOLDILOCKS"  # moderate growth, low inflation
    STAGFLATION = "STAGFLATION"  # low growth, high inflation
    RECESSION = "RECESSION"  # contracting economy
    RECOVERY = "RECOVERY"  # early cycle recovery
    TIGHTENING = "TIGHTENING"  # Fed tightening
    EASING = "EASING"  # Fed easing

    ENVIRONMENTS = [GROWTH_INFLATION, GOLDILOCKS, STAGFLATION, RECESSION,
                    RECOVERY, TIGHTENING, EASING]

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, macro: dict) -> dict:
        """Analyze macro environment (legacy interface).

        Returns simple dict for backward compatibility.
        """
        env = self.classify_environment(macro)
        return {"environment": env}

    def classify_environment(self, macro: dict) -> str:
        """Classify macroeconomic environment from data.

        Args:
            macro: dict with optional keys:
                - interest_rate: current policy rate (%)
                - rate_change: recent rate change (positive = hiking)
                - inflation: CPI/inflation rate (%)
                - inflation_trend: "rising", "falling", "stable"
                - gdp_growth: GDP growth rate (%)
                - yield_curve: 10Y-2Y spread (bps)
                - usd_index: USD index level
                - credit_spread: corporate credit spread (bps)
                - unemployment: unemployment rate (%)

        Returns:
            Macro environment string
        """
        growth = macro.get("gdp_growth", 2.0)
        inflation = macro.get("inflation", 2.0)
        rate_change = macro.get("rate_change", 0.0)
        yield_curve = macro.get("yield_curve", 100)

        # Recession: negative GDP growth
        if growth < 0:
            return self.RECESSION

        # Stagflation: low growth + high inflation
        if growth < 1.5 and inflation > 4:
            return self.STAGFLATION

        # Tightening: rates rising
        if rate_change > 0.25:
            return self.TIGHTENING

        # Easing: rates falling
        if rate_change < -0.25:
            return self.EASING

        # Goldilocks: moderate growth, moderate inflation
        if 2 <= growth <= 4 and inflation <= 3:
            return self.GOLDILOCKS

        # Growth with inflation
        if growth > 2 and inflation > 3:
            return self.GROWTH_INFLATION

        # Recovery: positive growth from low base
        if 0 < growth < 2:
            return self.RECOVERY

        return self.GOLDILOCKS  # default

    def analyze_detailed(self, macro: dict) -> dict:
        """Detailed macro analysis with scores."""
        env = self.classify_environment(macro)

        # Rate direction
        rate_change = macro.get("rate_change", 0.0)
        if rate_change > 0.5:
            rate_stance = "aggressive_hiking"
        elif rate_change > 0:
            rate_stance = "hiking"
        elif rate_change < -0.5:
            rate_stance = "aggressive_cutting"
        elif rate_change < 0:
            rate_stance = "cutting"
        else:
            rate_stance = "on_hold"

        # Inflation assessment
        inflation = macro.get("inflation", 2.0)
        if inflation > 5:
            inflation_stance = "high"
        elif inflation > 3:
            inflation_stance = "elevated"
        elif inflation > 2:
            inflation_stance = "moderate"
        elif inflation > 0:
            inflation_stance = "low"
        else:
            inflation_stance = "deflation"

        # Yield curve
        yc = macro.get("yield_curve", 100)
        if yc < 0:
            curve_stance = "inverted"
        elif yc < 50:
            curve_stance = "flattening"
        elif yc < 100:
            curve_stance = "normal"
        else:
            curve_stance = "steep"

        # Credit conditions
        credit = macro.get("credit_spread", 100)
        if credit > 400:
            credit_stance = "stressed"
        elif credit > 200:
            credit_stance = "tight"
        else:
            credit_stance = "normal"

        return {
            "environment": env,
            "rate_stance": rate_stance,
            "inflation_stance": inflation_stance,
            "curve_stance": curve_stance,
            "credit_stance": credit_stance,
            "gdp_growth": macro.get("gdp_growth"),
            "inflation": inflation,
            "interest_rate": macro.get("interest_rate"),
        }

    def to_macro_signal(self, environment: str) -> str:
        """Map macro environment to risk signal."""
        risk_on_envs = {self.GOLDILOCKS, self.RECOVERY, self.EASING}
        risk_off_envs = {self.RECESSION, self.STAGFLATION, self.TIGHTENING}

        if environment in risk_on_envs:
            return "RISK_ON"
        elif environment in risk_off_envs:
            return "RISK_OFF"
        else:
            return "RISK_ON"  # GROWTH_INFLATION defaults to risk-on

    def suggested_exposure(self, environment: str) -> float:
        """Suggest equity exposure based on macro environment."""
        exposure_map = {
            self.GOLDILOCKS: 1.0,
            self.RECOVERY: 0.9,
            self.EASING: 0.85,
            self.GROWTH_INFLATION: 0.7,
            self.TIGHTENING: 0.5,
            self.STAGFLATION: 0.4,
            self.RECESSION: 0.2,
        }
        return exposure_map.get(environment, 0.7)

    def regime_favorable_strategies(self, environment: str) -> List[str]:
        """Suggest strategy types favorable for this macro environment."""
        strategy_map = {
            self.GOLDILOCKS: ["momentum", "growth", "breakout"],
            self.RECOVERY: ["value", "cyclical", "momentum"],
            self.EASING: ["growth", "tech", "duration_sensitive"],
            self.GROWTH_INFLATION: ["commodity", "value", "inflation_hedge"],
            self.TIGHTENING: ["quality", "low_volatility", "defensive"],
            self.STAGFLATION: ["commodity", "gold", "defensive"],
            self.RECESSION: ["safe_haven", "bonds", "defensive", "inverse"],
        }
        return strategy_map.get(environment, ["neutral"])

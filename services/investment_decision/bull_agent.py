from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BullCaseAnalysis:
    symbol: str
    thesis: str = ""
    bullish_conviction: float = 0.0  # 0-1
    growth_drivers: List[str] = field(default_factory=list)
    catalysts: List[str] = field(default_factory=list)
    competitive_advantages: List[str] = field(default_factory=list)
    target_upside: float = 0.0
    narrative: str = ""
    required_conditions: List[str] = field(default_factory=list)
    conviction_level: str = "MEDIUM"


class BullCaseAgent:
    """Bull Case Agent - analyzes the bullish case for an investment."""

    def __init__(self):
        self.analyses: List[BullCaseAnalysis] = []

    def analyze(self, asset):
        """Analyze the bull case for an asset.

        Args:
            asset: The asset to analyze (str, dict, or BullCaseAnalysis).

        Returns:
            Dict containing the bull case analysis.
        """
        if isinstance(asset, BullCaseAnalysis):
            return self._process_analysis(asset)
        if isinstance(asset, dict):
            return self._analyze_dict(asset)
        return {"bull_case": asset}

    def _process_analysis(self, analysis: BullCaseAnalysis) -> dict:
        self.analyses.append(analysis)
        return {
            "bull_case": {
                "symbol": analysis.symbol,
                "thesis": analysis.thesis,
                "bullish_conviction": analysis.bullish_conviction,
                "growth_drivers": analysis.growth_drivers,
                "catalysts": analysis.catalysts,
                "competitive_advantages": analysis.competitive_advantages,
                "target_upside": round(analysis.target_upside, 2),
                "narrative": analysis.narrative,
                "required_conditions": analysis.required_conditions,
                "conviction_level": analysis.conviction_level,
            }
        }

    def _analyze_dict(self, data: dict) -> dict:
        symbol = data.get("symbol", "UNKNOWN")
        thesis_data = data.get("thesis", {})

        # Derive bull case from thesis data
        why_buy = thesis_data.get("why_buy", "")
        catalysts = thesis_data.get("catalyst", [])
        if isinstance(catalysts, str):
            catalysts = [catalysts] if catalysts else []

        # Calculate bullish conviction
        conviction = self._calculate_conviction(data)

        # Generate growth drivers
        growth_drivers = self._identify_growth_drivers(thesis_data)

        # Generate competitive advantages
        comp_advantages = self._identify_advantages(thesis_data)

        # Generate narrative
        narrative = self._build_narrative(symbol, why_buy, growth_drivers)

        # Determine conviction level
        conviction_level = self._determine_conviction_level(conviction)

        analysis = BullCaseAnalysis(
            symbol=symbol,
            thesis=thesis_data.get("title", ""),
            bullish_conviction=round(conviction, 2),
            growth_drivers=growth_drivers,
            catalysts=catalysts,
            competitive_advantages=comp_advantages,
            target_upside=thesis_data.get("expected_return", 0.15),
            narrative=narrative,
            required_conditions=self._derive_conditions(thesis_data),
            conviction_level=conviction_level,
        )
        self.analyses.append(analysis)
        return self._process_analysis(analysis)

    def _calculate_conviction(self, data: dict) -> float:
        base = 0.5
        thesis_data = data.get("thesis", {})
        if thesis_data.get("why_buy"):
            base += 0.1
        if thesis_data.get("why_now"):
            base += 0.1
        if thesis_data.get("catalyst"):
            base += 0.15
        if thesis_data.get("expected_return", 0) > 0.1:
            base += 0.1
        return min(1.0, base)

    def _identify_growth_drivers(self, thesis_data: dict) -> List[str]:
        drivers = []
        why_buy = thesis_data.get("why_buy", "").lower()
        why_now = thesis_data.get("why_now", "").lower()
        combined = f"{why_buy} {why_now}"

        keywords = {
            "ai": "AI technology adoption growth",
            "cloud": "Cloud computing expansion",
            "semiconductor": "Semiconductor demand cycle",
            "hbm": "HBM memory demand surge",
            "recovery": "Cyclical recovery momentum",
            "innovation": "Technology innovation pipeline",
            "market": "Market share expansion",
            "expansion": "Geographic expansion opportunity",
        }

        for keyword, driver in keywords.items():
            if keyword in combined:
                drivers.append(driver)

        if not drivers:
            drivers.append("General market growth opportunity")
        return drivers[:4]

    def _identify_advantages(self, thesis_data: dict) -> List[str]:
        advantages = []
        why_buy = thesis_data.get("why_buy", "").lower()

        advantage_keywords = {
            "moat": "Strong economic moat",
            "competitive": "Sustainable competitive advantage",
            "technology": "Technology leadership",
            "brand": "Brand strength and recognition",
            "network": "Network effects",
            "patent": "Patent-protected technology",
            "scale": "Economies of scale",
        }

        for keyword, advantage in advantage_keywords.items():
            if keyword in why_buy:
                advantages.append(advantage)

        if not advantages:
            advantages.append("Competitive market position")
        return advantages[:3]

    def _build_narrative(self, symbol: str, why_buy: str, drivers: List[str]) -> str:
        base = f"{symbol}: Bull case thesis. "
        if why_buy:
            base += f"{why_buy} "
        if drivers:
            base += f"Key growth drivers: {'; '.join(drivers[:3])}."
        return base

    def _determine_conviction_level(self, conviction: float) -> str:
        if conviction >= 0.8:
            return "VERY_HIGH"
        if conviction >= 0.6:
            return "HIGH"
        if conviction >= 0.4:
            return "MEDIUM"
        return "LOW"

    def _derive_conditions(self, thesis_data: dict) -> List[str]:
        conditions = [
            "Thesis catalyst materializes within expected timeframe",
            "No adverse macro regime change",
            "Sector trends remain supportive",
        ]
        if thesis_data.get("expected_return", 0) > 0.15:
            conditions.append("High return expectations require strong execution")
        return conditions

    def get_analyses(self, symbol: Optional[str] = None) -> List[BullCaseAnalysis]:
        """Get bull case analyses, optionally filtered by symbol."""
        if symbol:
            return [a for a in self.analyses if a.symbol == symbol]
        return list(self.analyses)

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BearCaseAnalysis:
    symbol: str
    thesis: str = ""
    risk_intensity: float = 0.0  # 0-1
    risk_factors: List[str] = field(default_factory=list)
    bubble_indicators: List[str] = field(default_factory=list)
    failure_scenarios: List[str] = field(default_factory=list)
    max_drawdown_estimate: float = 0.0
    narrative: str = ""
    invalidation_points: List[str] = field(default_factory=list)
    risk_level: str = "MEDIUM"


class BearCaseAgent:
    """Bear Case Agent - analyzes the bearish case and risks for an investment."""

    def __init__(self):
        self.analyses: List[BearCaseAnalysis] = []

    def analyze(self, asset):
        """Analyze the bear case for an asset.

        Args:
            asset: The asset to analyze (str, dict, or BearCaseAnalysis).

        Returns:
            Dict containing the bear case analysis.
        """
        if isinstance(asset, BearCaseAnalysis):
            return self._process_analysis(asset)
        if isinstance(asset, dict):
            return self._analyze_dict(asset)
        return {"bear_case": asset}

    def _process_analysis(self, analysis: BearCaseAnalysis) -> dict:
        self.analyses.append(analysis)
        return {
            "bear_case": {
                "symbol": analysis.symbol,
                "thesis": analysis.thesis,
                "risk_intensity": analysis.risk_intensity,
                "risk_factors": analysis.risk_factors,
                "bubble_indicators": analysis.bubble_indicators,
                "failure_scenarios": analysis.failure_scenarios,
                "max_drawdown_estimate": round(analysis.max_drawdown_estimate, 2),
                "narrative": analysis.narrative,
                "invalidation_points": analysis.invalidation_points,
                "risk_level": analysis.risk_level,
            }
        }

    def _analyze_dict(self, data: dict) -> dict:
        symbol = data.get("symbol", "UNKNOWN")
        thesis_data = data.get("thesis", {})

        # Calculate risk intensity
        risk_intensity = self._calculate_risk(data)

        # Identify risk factors
        risk_factors = self._identify_risks(thesis_data)

        # Identify bubble indicators
        bubble_indicators = self._check_bubble(data)

        # Generate failure scenarios
        failure_scenarios = self._generate_failure_scenarios(symbol, thesis_data)

        # Build narrative
        narrative = self._build_narrative(symbol, risk_factors, risk_intensity)

        # Determine risk level
        risk_level = self._determine_risk_level(risk_intensity)

        # Estimate max drawdown
        max_drawdown = self._estimate_drawdown(risk_intensity)

        analysis = BearCaseAnalysis(
            symbol=symbol,
            thesis=thesis_data.get("title", ""),
            risk_intensity=round(risk_intensity, 2),
            risk_factors=risk_factors,
            bubble_indicators=bubble_indicators,
            failure_scenarios=failure_scenarios,
            max_drawdown_estimate=round(max_drawdown, 2),
            narrative=narrative,
            invalidation_points=self._derive_invalidation_points(thesis_data),
            risk_level=risk_level,
        )
        self.analyses.append(analysis)
        return self._process_analysis(analysis)

    def _calculate_risk(self, data: dict) -> float:
        base = 0.3
        thesis_data = data.get("thesis", {})

        # Higher expected return often means higher risk
        if thesis_data.get("expected_return", 0) > 0.2:
            base += 0.15
        elif thesis_data.get("expected_return", 0) > 0.1:
            base += 0.05

        # Check risk mentions
        risks = thesis_data.get("risks", [])
        if isinstance(risks, list) and len(risks) > 3:
            base += 0.1

        # Lack of exit conditions increases risk
        exit_conds = thesis_data.get("exit_conditions", [])
        if not exit_conds:
            base += 0.1

        return min(1.0, base)

    def _identify_risks(self, thesis_data: dict) -> List[str]:
        risks = []
        explicit_risks = thesis_data.get("risks", [])
        if isinstance(explicit_risks, list):
            risks.extend(explicit_risks)

        if not risks:
            risks = [
                "Market regime shift risk",
                "Competitive threat risk",
                "Execution risk",
                "Valuation compression risk",
            ]

        return risks[:5]

    def _check_bubble(self, data: dict) -> List[str]:
        bubble_indicators = []
        thesis_data = data.get("thesis", {})

        expected_return = thesis_data.get("expected_return", 0)
        if expected_return > 0.3:
            bubble_indicators.append("Unusually high return expectations (>30%)")

        why_buy = thesis_data.get("why_buy", "").lower()
        bubble_keywords = ["parabolic", "to the moon", "can't lose", "guaranteed", "revolution"]
        for kw in bubble_keywords:
            if kw in why_buy:
                bubble_indicators.append(f"Euphoric language detected: '{kw}'")
                break

        return bubble_indicators

    def _generate_failure_scenarios(self, symbol: str, thesis_data: dict) -> List[str]:
        scenarios = []
        catalyst = thesis_data.get("catalyst", "")
        if isinstance(catalyst, str) and catalyst:
            scenarios.append(f"{symbol}: Catalyst '{catalyst}' fails to materialize")

        scenarios.append(f"{symbol}: Broader market downturn of 20%+")
        scenarios.append(f"{symbol}: Competitive disruption erodes market position")
        scenarios.append(f"{symbol}: Regulatory changes impact business model")

        return scenarios

    def _build_narrative(self, symbol: str, risks: List[str], intensity: float) -> str:
        risk_desc = "high" if intensity > 0.6 else "moderate" if intensity > 0.3 else "low"
        base = f"{symbol}: Bear case with {risk_desc} risk intensity. "
        if risks:
            base += f"Primary concerns: {'; '.join(risks[:2])}."
        return base

    def _determine_risk_level(self, intensity: float) -> str:
        if intensity >= 0.8:
            return "CRITICAL"
        if intensity >= 0.6:
            return "HIGH"
        if intensity >= 0.4:
            return "MEDIUM"
        return "LOW"

    def _estimate_drawdown(self, risk_intensity: float) -> float:
        if risk_intensity > 0.7:
            return 0.40
        if risk_intensity > 0.5:
            return 0.25
        if risk_intensity > 0.3:
            return 0.15
        return 0.10

    def _derive_invalidation_points(self, thesis_data: dict) -> List[str]:
        points = [
            "Thesis catalyst does not materialize within expected timeframe",
            "Sector fundamentals deteriorate significantly",
            "Company reports consecutive earnings misses",
        ]
        if thesis_data.get("expected_return", 0) > 0.2:
            points.append("High-growth narrative breaks down")
        return points

    def get_analyses(self, symbol: Optional[str] = None) -> List[BearCaseAnalysis]:
        """Get bear case analyses, optionally filtered by symbol."""
        if symbol:
            return [a for a in self.analyses if a.symbol == symbol]
        return list(self.analyses)

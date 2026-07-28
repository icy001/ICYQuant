"""Central Bank Intelligence Agent.

Analyzes central bank policy stances, statements, and forward guidance
for major central banks (Fed, ECB, BOJ, PBOC, BOE).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from .data import CentralBankEvent, MacroDataSnapshot, MacroIndicator


class PolicyStance(str, Enum):
    """Central bank policy stance."""
    AGGRESSIVE_HIKE = "aggressive_hike"
    HIKE = "hike"
    MODERATE_HIKE = "moderate_hike"
    HOLD_HAWKISH = "hold_hawkish"
    HOLD_NEUTRAL = "hold_neutral"
    HOLD_DOVISH = "hold_dovish"
    MODERATE_CUT = "moderate_cut"
    CUT = "cut"
    AGGRESSIVE_CUT = "aggressive_cut"
    UNKNOWN = "unknown"


class HawkDoveScale(str, Enum):
    """Hawkish-Dovish scale."""
    STRONG_HAWKISH = "strong_hawkish"
    HAWKISH = "hawkish"
    SLIGHTLY_HAWKISH = "slightly_hawkish"
    NEUTRAL = "neutral"
    SLIGHTLY_DOVISH = "slightly_dovish"
    DOVISH = "dovish"
    STRONG_DOVISH = "strong_dovish"


@dataclass
class CentralBankAnalysis:
    """Result of central bank analysis.

    Attributes:
        bank: Central bank identifier.
        stance: Current policy stance.
        hawk_dove: Hawkish-dovish positioning.
        rate_bias: Expected direction of next rate move.
        rate_change_probability: Probability of next meeting rate change (0-1).
        expected_bps: Expected basis point change at next meeting.
        confidence: Overall analysis confidence (0-1).
        key_themes: Extracted policy themes.
        risks_highlighted: Risks mentioned in communications.
        details: Additional analysis details.
        timestamp: Analysis timestamp.
    """
    bank: str
    stance: PolicyStance
    hawk_dove: HawkDoveScale
    rate_bias: str = "unchanged"  # "up", "down", "unchanged"
    rate_change_probability: float = 0.0
    expected_bps: float = 0.0
    confidence: float = 0.5
    key_themes: list[str] = field(default_factory=list)
    risks_highlighted: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_dovish(self) -> bool:
        return self.hawk_dove in (
            HawkDoveScale.DOVISH,
            HawkDoveScale.STRONG_DOVISH,
            HawkDoveScale.SLIGHTLY_DOVISH,
        )

    @property
    def is_hawkish(self) -> bool:
        return self.hawk_dove in (
            HawkDoveScale.HAWKISH,
            HawkDoveScale.STRONG_HAWKISH,
            HawkDoveScale.SLIGHTLY_HAWKISH,
        )

    @property
    def summary(self) -> str:
        return f"{self.bank}: {self.stance.value} ({self.hawk_dove.value})"


class CentralBankIntelligence:
    """Analyzes central bank policy and communications.

    Evaluates the current monetary policy stance for each major
    central bank based on rate levels, policy direction, balance
    sheet actions, and communication tone.
    """

    # Major central banks supported
    SUPPORTED_BANKS = {"FED", "ECB", "BOJ", "PBOC", "BOE", "RBA", "RBNZ", "BOC", "SNB"}

    # Policy rate thresholds (neutral rate estimates)
    _NEUTRAL_RATES: dict[str, float] = {
        "FED": 2.5,
        "ECB": 2.0,
        "BOJ": 0.5,
        "BOE": 2.5,
        "PBOC": 2.0,
        "RBA": 3.0,
        "RBNZ": 3.0,
        "BOC": 2.5,
        "SNB": 1.0,
    }

    # Dovish keyword patterns
    _DOVISH_KEYWORDS = [
        "accommodative", "support", "patient", "gradual",
        "below target", "slack", "dovish", "easing",
        "downside risks", "disinflation", "softening",
        "flexibility", "data dependent", "wait and see",
    ]

    # Hawkish keyword patterns
    _HAWKISH_KEYWORDS = [
        "vigilant", "inflation pressure", "overheating",
        "tightening", "restrictive", "above target",
        "upside risks", "wage pressure", "capacity constraints",
        "anchored", "credibility", "forceful",
    ]

    def __init__(self):
        self._analyses: dict[str, list[CentralBankAnalysis]] = {
            bank: [] for bank in self.SUPPORTED_BANKS
        }

    def analyze(self, event: CentralBankEvent,
                macro_snapshot: Optional[MacroDataSnapshot] = None) -> CentralBankAnalysis:
        """Analyze a central bank event and determine policy stance.

        Args:
            event: Central bank event data.
            macro_snapshot: Optional macro context for richer analysis.

        Returns:
            CentralBankAnalysis with stance and hawk-dove positioning.
        """
        # 1. Determine stance from rate action
        stance = self._determine_stance(event)

        # 2. Analyze communication tone
        hawk_dove = self._analyze_tone(event)

        # 3. Infer rate bias
        rate_bias = self._infer_bias(event, stance, hawk_dove)

        # 4. Estimate next move probability
        prob, expected_bps = self._estimate_next_move(event, stance, hawk_dove)

        # 5. Extract key themes
        themes = self._extract_themes(event)
        risks = self._extract_risks(event)

        analysis = CentralBankAnalysis(
            bank=event.bank,
            stance=stance,
            hawk_dove=hawk_dove,
            rate_bias=rate_bias,
            rate_change_probability=prob,
            expected_bps=expected_bps,
            confidence=event.confidence,
            key_themes=themes,
            risks_highlighted=risks,
            details={
                "event_type": event.event_type,
                "current_rate": event.current_rate,
                "rate_change": event.rate_change,
                "neutral_rate": self._NEUTRAL_RATES.get(event.bank),
            },
        )

        self._analyses[event.bank].append(analysis)
        return analysis

    def analyze_from_dict(self, data: dict[str, Any]) -> CentralBankAnalysis:
        """Analyze from a simple data dict.

        Convenience method for testing.

        Args:
            data: Dict with keys: bank, rate_change, current_rate,
                  statement_text, sentiment, confidence.

        Returns:
            CentralBankAnalysis result.
        """
        event = CentralBankEvent(
            bank=data.get("bank", "FED"),
            event_type=data.get("event_type", "decision"),
            date=data.get("date", datetime.utcnow()),
            rate_change=data.get("rate_change", 0.0),
            current_rate=data.get("current_rate", 5.0),
            statement_text=data.get("statement_text", data.get("statement", "")),
            sentiment=data.get("sentiment", "neutral"),
            confidence=data.get("confidence", 0.5),
        )
        return self.analyze(event)

    def get_history(self, bank: str) -> list[CentralBankAnalysis]:
        """Get analysis history for a central bank."""
        return list(self._analyses.get(bank, []))

    def get_latest(self, bank: str) -> Optional[CentralBankAnalysis]:
        """Get the most recent analysis for a bank."""
        history = self._analyses.get(bank, [])
        return history[-1] if history else None

    def get_all_latest(self) -> dict[str, Optional[CentralBankAnalysis]]:
        """Get latest analysis for all banks."""
        return {bank: self.get_latest(bank) for bank in self.SUPPORTED_BANKS}

    # ── Private helpers ─────────────────────────────────────────────

    def _determine_stance(self, event: CentralBankEvent) -> PolicyStance:
        """Determine policy stance from rate action."""
        rate_change = event.rate_change
        current_rate = event.current_rate
        neutral = self._NEUTRAL_RATES.get(event.bank, 2.5)

        if rate_change > 50:
            return PolicyStance.AGGRESSIVE_HIKE
        elif rate_change > 25:
            return PolicyStance.HIKE
        elif rate_change > 0:
            return PolicyStance.MODERATE_HIKE
        elif rate_change == 0:
            # Determine hold bias from rate level vs neutral
            if current_rate > neutral + 1.0:
                return PolicyStance.HOLD_HAWKISH
            elif current_rate < neutral - 0.5:
                return PolicyStance.HOLD_DOVISH
            else:
                return PolicyStance.HOLD_NEUTRAL
        elif rate_change > -25:
            return PolicyStance.MODERATE_CUT
        elif rate_change > -50:
            return PolicyStance.CUT
        else:
            return PolicyStance.AGGRESSIVE_CUT

    def _analyze_tone(self, event: CentralBankEvent) -> HawkDoveScale:
        """Analyze communication tone for hawkish/dovish bias."""
        sentiment = event.sentiment.lower()

        # If statement text is available, use keyword analysis
        # (more granular than simple sentiment label)
        if event.statement_text:
            return self._keyword_tone_analysis(event.statement_text)

        # Use explicit sentiment if provided (no statement text)
        if sentiment == "hawkish":
            return HawkDoveScale.HAWKISH
        elif sentiment == "dovish":
            return HawkDoveScale.DOVISH
        elif sentiment == "neutral":
            return HawkDoveScale.NEUTRAL

        # Default from rate change direction
        if event.rate_change > 25:
            return HawkDoveScale.HAWKISH
        elif event.rate_change < -25:
            return HawkDoveScale.DOVISH
        return HawkDoveScale.NEUTRAL

    def _keyword_tone_analysis(self, text: str) -> HawkDoveScale:
        """Analyze tone from keyword frequencies in statement text."""
        text_lower = text.lower()
        dovish_count = sum(1 for kw in self._DOVISH_KEYWORDS if kw in text_lower)
        hawkish_count = sum(1 for kw in self._HAWKISH_KEYWORDS if kw in text_lower)

        diff = dovish_count - hawkish_count
        if diff >= 3:
            return HawkDoveScale.STRONG_DOVISH
        elif diff >= 1:
            return HawkDoveScale.DOVISH
        elif diff <= -3:
            return HawkDoveScale.STRONG_HAWKISH
        elif diff <= -1:
            return HawkDoveScale.HAWKISH
        return HawkDoveScale.NEUTRAL

    def _infer_bias(self, event: CentralBankEvent,
                    stance: PolicyStance, hawk_dove: HawkDoveScale) -> str:
        """Infer the directional bias for the next policy move."""
        if stance in (PolicyStance.AGGRESSIVE_HIKE, PolicyStance.HIKE, PolicyStance.MODERATE_HIKE):
            return "up"
        if stance in (PolicyStance.AGGRESSIVE_CUT, PolicyStance.CUT, PolicyStance.MODERATE_CUT):
            return "down"

        # Holding — infer from tone
        if hawk_dove in (HawkDoveScale.STRONG_HAWKISH, HawkDoveScale.HAWKISH):
            return "up"
        if hawk_dove in (HawkDoveScale.STRONG_DOVISH, HawkDoveScale.DOVISH):
            return "down"
        return "unchanged"

    def _estimate_next_move(self, event: CentralBankEvent,
                            stance: PolicyStance,
                            hawk_dove: HawkDoveScale) -> tuple[float, float]:
        """Estimate probability and magnitude of next rate move."""
        # Base probability from stance
        prob = 0.0
        expected_bps = 0.0

        if stance in (PolicyStance.AGGRESSIVE_HIKE, PolicyStance.AGGRESSIVE_CUT):
            prob = 0.9
            expected_bps = 50.0
        elif stance in (PolicyStance.HIKE, PolicyStance.CUT):
            prob = 0.75
            expected_bps = 25.0
        elif stance in (PolicyStance.MODERATE_HIKE, PolicyStance.MODERATE_CUT):
            prob = 0.5
            expected_bps = 10.0
        elif stance == PolicyStance.HOLD_HAWKISH:
            prob = 0.4
            expected_bps = 15.0
        elif stance == PolicyStance.HOLD_DOVISH:
            prob = 0.4
            expected_bps = -15.0
        elif stance == PolicyStance.HOLD_NEUTRAL:
            prob = 0.2
            expected_bps = 0.0

        # Adjust by tone
        if hawk_dove in (HawkDoveScale.STRONG_HAWKISH, HawkDoveScale.STRONG_DOVISH):
            prob += 0.15
        elif hawk_dove in (HawkDoveScale.HAWKISH, HawkDoveScale.DOVISH):
            prob += 0.05

        # Direction from bias
        bias = self._infer_bias(event, stance, hawk_dove)
        if bias == "down":
            expected_bps = -abs(expected_bps)
        elif bias == "unchanged":
            expected_bps = 0.0

        return min(1.0, max(0.0, prob)), expected_bps

    def _extract_themes(self, event: CentralBankEvent) -> list[str]:
        """Extract key policy themes from statement."""
        themes: list[str] = []
        text = event.statement_text.lower()

        theme_patterns = {
            "inflation": ["inflation", "price stability", "cpi", "price pressure"],
            "employment": ["employment", "labor market", "jobs", "wage"],
            "growth": ["growth", "gdp", "economic activity", "output"],
            "financial stability": ["financial stability", "systemic risk", "leverage"],
            "global risks": ["global", "trade", "geopolitical", "spillover"],
            "housing": ["housing", "mortgage", "real estate"],
            "credit conditions": ["credit", "lending", "borrowing", "tightening"],
        }

        for theme, keywords in theme_patterns.items():
            if any(kw in text for kw in keywords):
                themes.append(theme)

        return themes

    def _extract_risks(self, event: CentralBankEvent) -> list[str]:
        """Extract highlighted risks from statement."""
        risks: list[str] = []
        text = event.statement_text.lower()

        risk_patterns = {
            "inflation upside": ["upside risk", "inflation risk", "price pressure"],
            "growth slowdown": ["slowdown", "contraction", "recession risk"],
            "labor market tightness": ["tight labor", "wage spiral", "labor shortage"],
            "financial instability": ["bubble", "excessive", "overvalued"],
            "external shock": ["external", "shock", "disruption", "war"],
        }

        for risk, keywords in risk_patterns.items():
            if any(kw in text for kw in keywords):
                risks.append(risk)

        return risks


__all__ = [
    "PolicyStance",
    "HawkDoveScale",
    "CentralBankAnalysis",
    "CentralBankIntelligence",
]

"""Volatility Regime Prediction.

Predicts future volatility regimes using VIX term structure analysis,
GARCH-style volatility forecasting, and multi-factor regime
classification to anticipate market environment transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VolatilityRegime(str, Enum):
    """Volatility regime classification."""

    LOW_VOL = "low_vol"
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH_VOL = "high_vol"
    EXTREME = "extreme"
    TAIL = "tail"


class RegimeTransition(str, Enum):
    """Regime transition direction."""

    STABLE = "stable"
    COOLING = "cooling"
    HEATING = "heating"
    REGIME_SHIFT = "regime_shift"


class TermStructureState(str, Enum):
    """VIX futures term structure state."""

    CONTANGO = "contango"
    FLAT = "flat"
    BACKWARDATION = "backwardation"
    SEVERE_BACKWARDATION = "severe_backwardation"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class VolatilityForecast:
    """Volatility forecast for multiple horizons.

    Attributes:
        current_vol: Current realized volatility (annualized).
        forecast_1d: 1-day ahead volatility forecast.
        forecast_5d: 5-day ahead volatility forecast.
        forecast_21d: 21-day ahead volatility forecast.
        forecast_63d: 63-day ahead volatility forecast.
        regime_probabilities: Probability distribution over regimes.
        term_structure: VIX futures term structure state.
        term_structure_slope: Slope of VIX term structure.
        persistence: Estimated volatility persistence (0-1).
        confidence: Forecast confidence [0.0, 1.0].
    """

    current_vol: float = 0.15
    forecast_1d: float = 0.15
    forecast_5d: float = 0.15
    forecast_21d: float = 0.15
    forecast_63d: float = 0.16
    regime_probabilities: dict[str, float] = field(default_factory=dict)
    term_structure: TermStructureState = TermStructureState.CONTANGO
    term_structure_slope: float = 0.0
    persistence: float = 0.7
    confidence: float = 0.5

    @property
    def dominant_regime(self) -> str:
        if not self.regime_probabilities:
            return "normal"
        return max(self.regime_probabilities, key=self.regime_probabilities.__getitem__)

    @property
    def trend(self) -> str:
        """Volatility trend direction."""
        if self.forecast_21d > self.current_vol * 1.15:
            return "increasing"
        elif self.forecast_21d < self.current_vol * 0.85:
            return "decreasing"
        return "stable"


@dataclass
class RegimePrediction:
    """Volatility regime prediction result.

    Attributes:
        current_regime: Current volatility regime.
        predicted_regime: Predicted regime for the forecast horizon.
        transition: Transition direction.
        forecast: Detailed volatility forecast.
        horizon_days: Forecast horizon in days.
        regime_shift_probability: Probability of a regime shift.
        description: Human-readable summary.
        confidence: Prediction confidence [0.0, 1.0].
        timestamp: Prediction timestamp.
    """

    current_regime: VolatilityRegime = VolatilityRegime.NORMAL
    predicted_regime: VolatilityRegime = VolatilityRegime.NORMAL
    transition: RegimeTransition = RegimeTransition.STABLE
    forecast: VolatilityForecast | None = None
    horizon_days: int = 21
    regime_shift_probability: float = 0.0
    description: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_heating_up(self) -> bool:
        return self.transition in (
            RegimeTransition.HEATING,
            RegimeTransition.REGIME_SHIFT,
        )

    @property
    def requires_defense(self) -> bool:
        return self.predicted_regime in (
            VolatilityRegime.HIGH_VOL,
            VolatilityRegime.EXTREME,
            VolatilityRegime.TAIL,
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class VolatilityRegimePredictor:
    """Predicts future volatility regimes using multi-factor analysis.

    Uses VIX term structure, GARCH-style persistence estimation,
    and volatility clustering dynamics to forecast regime transitions.

    Attributes:
        vol_history: Historical volatility readings.
        vix_history: Historical VIX readings.
        term_structure_history: VIX term structure readings.
    """

    # Regime thresholds (VIX-based)
    REGIME_THRESHOLDS: dict[VolatilityRegime, float] = {
        VolatilityRegime.LOW_VOL: 12.0,
        VolatilityRegime.NORMAL: 18.0,
        VolatilityRegime.ELEVATED: 25.0,
        VolatilityRegime.HIGH_VOL: 35.0,
        VolatilityRegime.EXTREME: 50.0,
        VolatilityRegime.TAIL: 80.0,
    }

    def __init__(self) -> None:
        self.vol_history: list[float] = []
        self.vix_history: list[float] = []
        self.term_structure_history: list[dict[str, float]] = []

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def predict(self,
                current_vol: float = 0.15,
                vix: float = 15.0,
                vix_1m: float | None = None,
                vix_3m: float | None = None,
                vix_6m: float | None = None,
                vol_of_vol: float = 0.0,
                horizon_days: int = 21) -> RegimePrediction:
        """Predict future volatility regime.

        Args:
            current_vol: Current realized volatility (annualized).
            vix: Current VIX (30-day implied vol).
            vix_1m: 1-month VIX futures price.
            vix_3m: 3-month VIX futures price.
            vix_6m: 6-month VIX futures price.
            vol_of_vol: Volatility of volatility.
            horizon_days: Forecast horizon in days.

        Returns:
            RegimePrediction with forecast and transition analysis.
        """
        self.vix_history.append(vix)
        self.vol_history.append(current_vol)
        for hist in (self.vix_history, self.vol_history):
            if len(hist) > 200:
                hist[:] = hist[-200:]

        # Term structure analysis
        ts_state, ts_slope = self._analyze_term_structure(vix, vix_1m, vix_3m, vix_6m)
        if vix_1m is not None and vix_3m is not None and vix_6m is not None:
            self.term_structure_history.append({
                "spot": vix, "1m": vix_1m, "3m": vix_3m, "6m": vix_6m,
            })
            if len(self.term_structure_history) > 100:
                self.term_structure_history[:] = self.term_structure_history[-100:]

        # Persistence estimation (GARCH-style)
        persistence = self._estimate_persistence()

        # Regime classification
        current_regime = self._classify_regime(vix)
        predicted_regime = self._forecast_regime(
            vix, persistence, vol_of_vol, ts_state, horizon_days,
        )

        # Transition analysis
        transition = self._detect_transition(current_regime, predicted_regime, vix,
                                              persistence, vol_of_vol, ts_state)

        regime_shift_prob = self._estimate_shift_probability(
            current_regime, vix, persistence, vol_of_vol, ts_state,
        )

        # Build forecast
        forecast = self._build_forecast(
            current_vol, vix, persistence, vol_of_vol, ts_state, ts_slope,
        )

        # Confidence
        confidence = self._compute_confidence(
            current_regime, vix, persistence, len(self.vix_history),
        )

        description = self._generate_description(
            current_regime, predicted_regime, transition,
            regime_shift_prob, ts_state, forecast,
        )

        return RegimePrediction(
            current_regime=current_regime,
            predicted_regime=predicted_regime,
            transition=transition,
            forecast=forecast,
            horizon_days=horizon_days,
            regime_shift_probability=regime_shift_prob,
            description=description,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Term Structure Analysis
    # ------------------------------------------------------------------

    def _analyze_term_structure(self, spot: float,
                                 vix_1m: float | None = None,
                                 vix_3m: float | None = None,
                                 vix_6m: float | None = None) -> tuple[TermStructureState, float]:
        """Analyze VIX term structure state."""
        if vix_1m is None or vix_3m is None:
            return TermStructureState.CONTANGO, 0.0

        slope = vix_3m - vix_1m
        if vix_1m < spot:
            if vix_1m < spot * 0.85:
                return TermStructureState.SEVERE_BACKWARDATION, slope
            return TermStructureState.BACKWARDATION, slope
        elif slope > 2.0:
            return TermStructureState.CONTANGO, slope
        elif slope > 0:
            return TermStructureState.FLAT, slope
        else:
            return TermStructureState.BACKWARDATION, slope

    # ------------------------------------------------------------------
    # Regime Classification
    # ------------------------------------------------------------------

    def _classify_regime(self, vix: float) -> VolatilityRegime:
        """Classify current volatility regime from VIX."""
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.TAIL]:
            return VolatilityRegime.TAIL
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.EXTREME]:
            return VolatilityRegime.EXTREME
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.HIGH_VOL]:
            return VolatilityRegime.HIGH_VOL
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.ELEVATED]:
            return VolatilityRegime.ELEVATED
        if vix >= self.REGIME_THRESHOLDS[VolatilityRegime.NORMAL]:
            return VolatilityRegime.NORMAL
        return VolatilityRegime.LOW_VOL

    def _forecast_regime(self, vix: float, persistence: float,
                         vol_of_vol: float, ts_state: TermStructureState,
                         horizon_days: int) -> VolatilityRegime:
        """Forecast future volatility regime."""
        # Mean-reversion speed
        mr_speed = 1.0 - persistence  # Higher persistence = slower mean-reversion
        long_term_vix = 18.0

        # Forecast: weighted by persistence toward mean
        daily_mr = mr_speed / 252
        fudge = (1.0 - daily_mr) ** horizon_days
        forecast_vix = fudge * vix + (1.0 - fudge) * long_term_vix

        # Adjust for vol-of-vol (uncertainty widens the distribution)
        vol_impact = vol_of_vol * forecast_vix * (horizon_days / 21) ** 0.5
        forecast_vix += vol_impact * 0.5

        # Term structure correction
        if ts_state == TermStructureState.SEVERE_BACKWARDATION:
            forecast_vix *= 0.85  # Market expects vol to decline
        elif ts_state == TermStructureState.BACKWARDATION:
            forecast_vix *= 0.92
        elif ts_state == TermStructureState.CONTANGO:
            forecast_vix *= 1.05  # Market expects vol to rise
        # else flat: no adjustment

        return self._classify_regime(forecast_vix)

    # ------------------------------------------------------------------
    # Persistence Estimation (GARCH-style)
    # ------------------------------------------------------------------

    def _estimate_persistence(self) -> float:
        """Estimate volatility persistence from history."""
        if len(self.vol_history) < 5:
            return 0.7  # Default persistence

        # Simple autocorrelation of squared returns proxy
        recent = self.vol_history[-min(30, len(self.vol_history)):]
        if len(recent) < 3:
            return 0.7

        # Compute lag-1 autocorrelation of volatilities
        n = len(recent)
        mean_vol = sum(recent) / n
        num = sum((recent[i] - mean_vol) * (recent[i + 1] - mean_vol)
                  for i in range(n - 1))
        den = sum((v - mean_vol) ** 2 for v in recent)
        if den == 0:
            return 0.7
        persistence = max(0.0, min(0.99, num / den)) if den != 0 else 0.7
        return max(0.5, persistence)  # Floor at 0.5 for stability

    # ------------------------------------------------------------------
    # Transition Detection
    # ------------------------------------------------------------------

    def _detect_transition(self, current: VolatilityRegime,
                           predicted: VolatilityRegime, vix: float,
                           persistence: float, vol_of_vol: float,
                           ts_state: TermStructureState) -> RegimeTransition:
        """Detect regime transition direction."""
        if current == predicted:
            return RegimeTransition.STABLE

        regimes = list(VolatilityRegime)
        cur_idx = regimes.index(current)
        pred_idx = regimes.index(predicted)

        if pred_idx > cur_idx + 1:
            return RegimeTransition.REGIME_SHIFT
        elif pred_idx > cur_idx:
            return RegimeTransition.HEATING
        elif pred_idx < cur_idx:
            return RegimeTransition.COOLING
        return RegimeTransition.STABLE

    def _estimate_shift_probability(self, current: VolatilityRegime,
                                      vix: float, persistence: float,
                                      vol_of_vol: float,
                                      ts_state: TermStructureState) -> float:
        """Estimate probability of regime shift."""
        base_prob = 0.05

        # Vol-of-vol contributes uncertainty
        if vol_of_vol > 0.5:
            base_prob += 0.2
        elif vol_of_vol > 0.3:
            base_prob += 0.1

        # Low persistence → more likely to shift
        if persistence < 0.6:
            base_prob += 0.1

        # Term structure signals
        if ts_state == TermStructureState.SEVERE_BACKWARDATION:
            base_prob += 0.15
        elif ts_state == TermStructureState.BACKWARDATION:
            base_prob += 0.05

        # Already extreme → higher shift probability (both directions)
        if current in (VolatilityRegime.HIGH_VOL, VolatilityRegime.EXTREME):
            base_prob += 0.1

        return min(0.95, base_prob)

    # ------------------------------------------------------------------
    # Forecast Building
    # ------------------------------------------------------------------

    def _build_forecast(self, current_vol: float, vix: float,
                        persistence: float, vol_of_vol: float,
                        ts_state: TermStructureState,
                        ts_slope: float) -> VolatilityForecast:
        """Build multi-horizon volatility forecast."""
        mr_speed = 1.0 - persistence
        long_term = 0.15

        def _project(days: int) -> float:
            daily_decay = (1.0 - mr_speed / 252) ** days
            fwd = daily_decay * current_vol + (1.0 - daily_decay) * long_term

            # Term structure adjustment
            if ts_state == TermStructureState.SEVERE_BACKWARDATION:
                fwd *= 0.85
            elif ts_state == TermStructureState.BACKWARDATION:
                fwd *= 0.92
            elif ts_state == TermStructureState.CONTANGO:
                fwd *= 1.05

            # Uncertainty band
            vol_component = vol_of_vol * fwd * (days / 21) ** 0.5 * 0.3
            return round(fwd + vol_component, 4)

        # Regime probabilities
        regime_probs = self._compute_regime_probabilities(
            current_vol, vix, persistence, ts_state,
        )

        return VolatilityForecast(
            current_vol=current_vol,
            forecast_1d=_project(1),
            forecast_5d=_project(5),
            forecast_21d=_project(21),
            forecast_63d=_project(63),
            regime_probabilities=regime_probs,
            term_structure=ts_state,
            term_structure_slope=ts_slope,
            persistence=persistence,
            confidence=0.5 + 0.1 * min(len(self.vix_history), 5),
        )

    def _compute_regime_probabilities(self, current_vol: float, vix: float,
                                        persistence: float,
                                        ts_state: TermStructureState) -> dict[str, float]:
        """Compute probability distribution over regimes for 21d forward."""
        forecast_vix = self._forecast_regime(vix, persistence, 0.0, ts_state, 21)
        # Convert to numeric index for probability distribution
        regimes = list(VolatilityRegime)
        pred_idx = regimes.index(forecast_vix)

        probs: dict[str, float] = {}
        total_prob = 0.0

        for i, reg in enumerate(regimes):
            dist = abs(i - pred_idx)
            if dist == 0:
                p = 0.45
            elif dist == 1:
                p = 0.25
            elif dist == 2:
                p = 0.15
            else:
                p = 0.05
            probs[reg.value] = p
            total_prob += p

        # Normalize
        if total_prob > 0:
            for k in probs:
                probs[k] = round(probs[k] / total_prob, 3)

        return probs

    # ------------------------------------------------------------------
    # Confidence & Description
    # ------------------------------------------------------------------

    def _compute_confidence(self, current: VolatilityRegime, vix: float,
                            persistence: float, history_len: int) -> float:
        confidence = 0.35
        if history_len > 30:
            confidence += 0.1
        if history_len > 60:
            confidence += 0.1
        if persistence > 0.8:
            confidence += 0.1  # High persistence = predictable
        if current in (VolatilityRegime.ELEVATED, VolatilityRegime.HIGH_VOL):
            confidence += 0.1
        return min(0.95, confidence)

    def _generate_description(self, current: VolatilityRegime,
                                predicted: VolatilityRegime,
                                transition: RegimeTransition,
                                shift_prob: float,
                                ts_state: TermStructureState,
                                forecast: VolatilityForecast) -> str:
        trans_desc = {
            RegimeTransition.STABLE: "stable",
            RegimeTransition.HEATING: "heating up",
            RegimeTransition.COOLING: "cooling down",
            RegimeTransition.REGIME_SHIFT: "undergoing regime shift",
        }
        current_label = current.value.replace("_", " ").title()
        predicted_label = predicted.value.replace("_", " ").title()
        ts_label = ts_state.value.replace("_", " ").title()

        if transition == RegimeTransition.STABLE:
            return (f"Volatility regime {trans_desc[transition]} at "
                    f"{current_label}. Term structure: {ts_label}."
                    f" (confidence={forecast.confidence:.2f})")
        else:
            return (f"Volatility regime {trans_desc[transition]} from "
                    f"{current_label} → {predicted_label}. "
                    f"Shift probability: {shift_prob:.1%}. "
                    f"Term structure: {ts_label}."
                    f" (confidence={forecast.confidence:.2f})")

    # ------------------------------------------------------------------
    # Quick Scan
    # ------------------------------------------------------------------

    def quick_scan(self, vix: float = 15.0) -> dict[str, Any]:
        """Fast regime scan from VIX alone."""
        regime = self._classify_regime(vix)
        return {
            "regime": regime.value,
            "vix": vix,
            "is_stressed": regime in (
                VolatilityRegime.HIGH_VOL,
                VolatilityRegime.EXTREME,
                VolatilityRegime.TAIL,
            ),
            "thresholds": {
                r.value: t for r, t in self.REGIME_THRESHOLDS.items()
            },
        }

    def clear(self) -> None:
        self.vol_history.clear()
        self.vix_history.clear()
        self.term_structure_history.clear()

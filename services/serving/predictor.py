"""Online Predictor — high-level prediction interface.

Provides unified predict/predict_batch/predict_portfolio APIs
that combine feature joining, model routing, inference, and caching
into a single call for strategy engines.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PredictSignal(str, Enum):
    """Trading signal derived from prediction."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class PredictRequest:
    """Single prediction request.

    Attributes:
        symbol: Trading symbol.
        features: Optional pre-computed features. If None, auto-joined.
        model_name: Optional model override. If None, routed automatically.
        market: Market segment (US, CN, FUTURES, etc).
        timestamp: Request timestamp.
    """

    symbol: str
    features: Optional[Dict[str, float]] = None
    model_name: Optional[str] = None
    market: str = "US"
    timestamp: float = field(default_factory=time.time)


@dataclass
class PredictResult:
    """Single prediction result.

    Attributes:
        symbol: Trading symbol.
        prediction: Raw model output.
        confidence: Prediction confidence [0, 1].
        signal: Derived trading signal.
        model_name: Model that produced prediction.
        latency_ms: End-to-end latency.
        cached: Whether result came from cache.
        metadata: Additional info.
    """

    symbol: str
    prediction: float
    confidence: Optional[float] = None
    signal: PredictSignal = PredictSignal.HOLD
    model_name: str = ""
    latency_ms: float = 0.0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "signal": self.signal.value,
            "model_name": self.model_name,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
            "metadata": self.metadata,
        }


class OnlinePredictor:
    """High-level predictor combining feature join, routing, inference, and caching.

    The main entry point for strategy engines to obtain model predictions.

    Usage::

        predictor = OnlinePredictor(
            inference_engine=engine,
            feature_joiner=joiner,
            model_router=router,
            prediction_cache=cache,
        )
        result = predictor.predict(PredictRequest(symbol="NVDA"))
        results = predictor.predict_batch([req1, req2, req3])
    """

    def __init__(
        self,
        inference_engine: Any = None,
        feature_joiner: Any = None,
        model_router: Any = None,
        prediction_cache: Any = None,
    ):
        self._engine = inference_engine
        self._joiner = feature_joiner
        self._router = model_router
        self._cache = prediction_cache

    def predict(self, request: PredictRequest) -> PredictResult:
        """Single online prediction with full pipeline.

        Flow: Cache check → Feature join → Model route → Inference → Cache store
        """
        start = time.perf_counter()

        # 1. Check prediction cache
        if self._cache:
            cached = self._cache.get(request.symbol, request.model_name)
            if cached is not None:
                latency = (time.perf_counter() - start) * 1000
                return PredictResult(
                    symbol=request.symbol,
                    prediction=cached.prediction,
                    confidence=cached.confidence,
                    signal=self._prediction_to_signal(cached.prediction),
                    model_name=cached.model_name,
                    latency_ms=round(latency, 3),
                    cached=True,
                )

        # 2. Join features if not provided
        features = request.features
        if features is None and self._joiner:
            join_result = self._joiner.join(request.symbol, request.market)
            features = join_result.features

        if features is None:
            raise ValueError(f"No features available for {request.symbol}")

        # 3. Route to model
        model_name = request.model_name
        model = None
        if self._router and model_name is None:
            route = self._router.route(request.symbol, request.market)
            model_name = route.model_name
            model = route.model
        elif self._router and model_name:
            route = self._router.get_model(model_name)
            if route:
                model = route.model

        if model is None:
            raise RuntimeError(f"No model available for {request.symbol} (name={model_name})")

        # 4. Run inference
        prediction, confidence = self._engine.predict(model, features, model_name or "")

        # 5. Store in cache
        if self._cache:
            self._cache.set(request.symbol, prediction, confidence, model_name or "")

        latency = (time.perf_counter() - start) * 1000

        return PredictResult(
            symbol=request.symbol,
            prediction=prediction,
            confidence=confidence,
            signal=self._prediction_to_signal(prediction),
            model_name=model_name or "",
            latency_ms=round(latency, 3),
            metadata={"features_count": len(features)},
        )

    def predict_batch(self, requests: List[PredictRequest]) -> List[PredictResult]:
        """Batch prediction for multiple symbols."""
        results: List[PredictResult] = []
        for req in requests:
            try:
                results.append(self.predict(req))
            except Exception as e:
                results.append(PredictResult(
                    symbol=req.symbol,
                    prediction=0.0,
                    signal=PredictSignal.HOLD,
                    metadata={"error": str(e)},
                ))
        return results

    def predict_portfolio(
        self,
        symbols: List[str],
        market: str = "US",
        features_dict: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, PredictResult]:
        """Predict for an entire portfolio.

        Args:
            symbols: List of trading symbols.
            market: Market segment.
            features_dict: Optional pre-computed features per symbol.

        Returns:
            Dict mapping symbol → PredictResult.
        """
        results: Dict[str, PredictResult] = {}
        for symbol in symbols:
            feats = features_dict.get(symbol) if features_dict else None
            result = self.predict(PredictRequest(symbol=symbol, features=feats, market=market))
            results[symbol] = result
        return results

    @staticmethod
    def _prediction_to_signal(prediction: float, threshold: float = 0.5) -> PredictSignal:
        """Convert raw prediction to trading signal."""
        if prediction > threshold:
            return PredictSignal.BUY
        elif prediction < (1.0 - threshold):
            return PredictSignal.SELL
        return PredictSignal.HOLD


class BatchPredictor:
    """Dedicated batch predictor for offline/bulk predictions.

    Optimized for throughput over latency — uses the inference engine's
    batch methods directly rather than individual predict calls.
    """

    def __init__(self, inference_engine: Any):
        self._engine = inference_engine

    def predict(
        self,
        model: Any,
        features_list: List[Dict[str, float]],
        symbols: Optional[List[str]] = None,
        model_name: str = "",
    ) -> Any:
        """Run batch inference and return BatchInferenceResult."""
        return self._engine.predict_batch(model, features_list, symbols, model_name)

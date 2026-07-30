"""State Encoder — transforms raw market data into RL state representations.

Converts complex market features (prices, volumes, technical indicators,
sentiment) into compact, informative state vectors for policy networks.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import math

import numpy as np


@dataclass
class EncoderConfig:
    """Configuration for the state encoder."""

    # Feature dimensions
    price_features: int = 4  # OHLCV compressed
    technical_features: int = 8  # RSI, MACD, BB, etc.
    volume_features: int = 3  # Volume profile
    sentiment_features: int = 2  # News sentiment, social
    portfolio_features: int = 6  # Positions, cash, exposure

    # Encoding
    use_attention: bool = True
    normalization: str = "zscore"  # zscore, minmax, none
    history_window: int = 50
    embedding_dim: int = 64
    dropout_rate: float = 0.1

    # Market-specific
    symbols: List[str] = field(default_factory=list)
    include_volatility: bool = True
    include_correlations: bool = False


@dataclass
class MarketEmbedding:
    """Learned market embedding vector."""

    vector: np.ndarray
    trend_score: float = 0.0
    volatility_score: float = 0.0
    momentum_score: float = 0.0
    sentiment_score: float = 0.0
    risk_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncodedState:
    """Full encoded state for RL agent."""

    # Core state vector
    state_vector: np.ndarray

    # Market embeddings
    market_embedding: MarketEmbedding

    # Portfolio state
    portfolio_embedding: np.ndarray

    # Normalized features
    normalized_prices: Dict[str, np.ndarray] = field(default_factory=dict)
    normalized_volumes: Dict[str, np.ndarray] = field(default_factory=dict)

    # Risk features
    risk_features: Dict[str, float] = field(default_factory=dict)

    # History
    history_window: int = 0

    def to_flat_vector(self) -> np.ndarray:
        """Get flat state vector for policy network input."""
        return self.state_vector


class StateEncoder:
    """Encodes raw market data into RL-ready state representations.

    Pipeline:
        1. Raw features → Normalization
        2. Technical indicators computation
        3. Feature concatenation
        4. Market embedding generation
        5. Final state vector output

    Usage:
        encoder = StateEncoder(config)
        state = encoder.encode(price_data, volume_data, portfolio_state)
    """

    def __init__(self, config: Optional[EncoderConfig] = None):
        self.config = config or EncoderConfig()
        self._price_history: Dict[str, List[float]] = {}
        self._volume_history: Dict[str, List[float]] = {}
        self._feature_stats: Dict[str, Dict[str, float]] = {}

    def encode(
        self,
        prices: Dict[str, float],
        volumes: Dict[str, float],
        portfolio_state: Dict[str, float],
        sentiment: float = 0.0,
        volatility: Optional[Dict[str, float]] = None,
    ) -> EncodedState:
        """Encode current market state into RL-compatible representation.

        Args:
            prices: Current prices per symbol
            volumes: Current volumes per symbol
            portfolio_state: Dict with cash, positions, exposure
            sentiment: Market sentiment score [-1, 1]
            volatility: Optional volatility per symbol

        Returns:
            EncodedState with state vector and metadata
        """
        # Update history
        for symbol, price in prices.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = []
                self._volume_history[symbol] = []
            self._price_history[symbol].append(price)
            self._volume_history[symbol].append(volumes.get(symbol, 0.0))
            # Keep window
            if len(self._price_history[symbol]) > self.config.history_window * 2:
                self._price_history[symbol] = self._price_history[symbol][
                    -self.config.history_window * 2:
                ]
                self._volume_history[symbol] = self._volume_history[symbol][
                    -self.config.history_window * 2:
                ]

        # 1. Compute technical features
        tech_features = self._compute_technical_features(prices)

        # 2. Compute price features (returns, volatility)
        price_features = self._compute_price_features(prices)

        # 3. Compute volume features
        vol_features = self._compute_volume_features(volumes)

        # 4. Portfolio features
        portfolio_features = self._compute_portfolio_features(portfolio_state)

        # 5. Sentiment features
        sentiment_features = np.array([sentiment, abs(sentiment)], dtype=np.float32)

        # 6. Normalize and concatenate
        all_features = np.concatenate([
            price_features,
            tech_features,
            vol_features,
            portfolio_features,
            sentiment_features,
        ])

        # Normalize
        all_features = self._normalize(all_features)

        # Generate market embedding (simplified: projection to embedding dim)
        embedding_vec = self._generate_embedding(all_features)

        market_emb = MarketEmbedding(
            vector=embedding_vec,
            trend_score=self._compute_trend_score(prices),
            volatility_score=self._compute_volatility_score(volatility),
            momentum_score=self._compute_momentum_score(),
            sentiment_score=sentiment,
            risk_score=self._compute_risk_score(portfolio_state),
        )

        # Portfolio embedding
        port_emb = self._normalize(portfolio_features)

        # Risk features
        risk_features = {
            "exposure": portfolio_state.get("exposure", 0.0),
            "leverage": portfolio_state.get("leverage", 0.0),
            "drawdown": portfolio_state.get("drawdown", 0.0),
            "var_95": portfolio_state.get("var", 0.02),
        }

        return EncodedState(
            state_vector=all_features,
            market_embedding=market_emb,
            portfolio_embedding=port_emb,
            normalized_prices={
                s: self._normalize(np.array(self._price_history.get(s, [])))
                for s in prices
            },
            normalized_volumes={
                s: self._normalize(np.array(self._volume_history.get(s, [])))
                for s in prices
            },
            risk_features=risk_features,
            history_window=self.config.history_window,
        )

    def _compute_technical_features(
        self, prices: Dict[str, float]
    ) -> np.ndarray:
        """Compute technical indicators as features."""
        features = []
        for symbol in sorted(prices.keys()):
            history = self._price_history.get(symbol, [prices[symbol]])
            if len(history) < 2:
                features.extend([0.0] * 8)
                continue

            # RSI (simplified 14-period)
            rsi = self._compute_rsi(history, 14)
            # MACD (simplified)
            macd = self._compute_macd(history)
            # Bollinger Bands position
            bb_pos = self._compute_bb_position(history, 20)
            # Rate of change
            roc = (prices[symbol] - history[-min(10, len(history))]) / (
                history[-min(10, len(history))] + 1e-8
            )
            # Moving average crossover
            ma_cross = self._compute_ma_crossover(history)

            features.extend([rsi, macd, bb_pos, roc, ma_cross, 0.0, 0.0, 0.0])

        return np.array(features[:self.config.technical_features], dtype=np.float32)

    def _compute_price_features(
        self, prices: Dict[str, float]
    ) -> np.ndarray:
        """Compute price-based features."""
        features = []
        for symbol in sorted(prices.keys()):
            history = self._price_history.get(symbol, [prices[symbol]])
            price = prices[symbol]
            ret_1d = (price - history[-2]) / history[-2] if len(history) >= 2 else 0.0
            ret_5d = (price - history[-min(5, len(history))]) / (
                history[-min(5, len(history))] + 1e-8
            )
            ret_20d = (price - history[-min(20, len(history))]) / (
                history[-min(20, len(history))] + 1e-8
            )
            log_price = math.log(price) if price > 0 else 0.0

            features.extend([ret_1d, ret_5d, ret_20d, log_price / 10.0])

        return np.array(features, dtype=np.float32)

    def _compute_volume_features(
        self, volumes: Dict[str, float]
    ) -> np.ndarray:
        """Compute volume-based features."""
        features = []
        for symbol in sorted(volumes.keys()):
            vol = volumes.get(symbol, 0.0)
            vwap = self._volume_history.get(symbol, [vol])
            vol_ma = np.mean(vwap[-20:]) if len(vwap) >= 20 else vol
            vol_ratio = vol / (vol_ma + 1e-8)
            features.extend([vol_ratio, math.log(vol + 1), 0.0])

        return np.array(features[:self.config.volume_features], dtype=np.float32)

    def _compute_portfolio_features(
        self, portfolio_state: Dict[str, float]
    ) -> np.ndarray:
        """Compute portfolio state features."""
        cash = portfolio_state.get("cash", 0.0)
        positions = portfolio_state.get("positions", 0.0)
        exposure = portfolio_state.get("exposure", 0.0)
        leverage = portfolio_state.get("leverage", 0.0)
        drawdown = portfolio_state.get("drawdown", 0.0)
        var_95 = portfolio_state.get("var", 0.02)

        return np.array(
            [cash / 1e6, positions, exposure, leverage, drawdown, var_95],
            dtype=np.float32,
        )

    def _compute_rsi(self, prices: List[float], period: int = 14) -> float:
        """Compute simplified RSI."""
        if len(prices) < period + 1:
            return 50.0
        gains = 0.0
        losses = 0.0
        for i in range(-period, 0):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains += change
            else:
                losses -= change
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100.0 - 100.0 / (1.0 + rs)

    def _compute_macd(self, prices: List[float]) -> float:
        """Compute simplified MACD histogram."""
        if len(prices) < 26:
            return 0.0
        ema12 = np.mean(prices[-12:])
        ema26 = np.mean(prices[-26:])
        return (ema12 - ema26) / (ema26 + 1e-8)

    def _compute_bb_position(
        self, prices: List[float], period: int = 20
    ) -> float:
        """Compute position within Bollinger Bands."""
        if len(prices) < period:
            return 0.0
        window = prices[-period:]
        ma = np.mean(window)
        std = np.std(window)
        if std == 0:
            return 0.0
        return (prices[-1] - ma) / (2 * std)  # 0 = middle, ±1 = bands

    def _compute_ma_crossover(self, prices: List[float]) -> float:
        """Compute moving average crossover signal."""
        if len(prices) < 20:
            return 0.0
        ma5 = np.mean(prices[-5:])
        ma20 = np.mean(prices[-20:])
        return (ma5 - ma20) / (ma20 + 1e-8)

    def _compute_trend_score(self, prices: Dict[str, float]) -> float:
        """Compute aggregate trend score."""
        scores = []
        for symbol, price in prices.items():
            history = self._price_history.get(symbol, [price])
            if len(history) < 20:
                continue
            ma20 = np.mean(history[-20:])
            scores.append((price - ma20) / (ma20 + 1e-8))
        return float(np.mean(scores)) if scores else 0.0

    def _compute_volatility_score(
        self, volatility: Optional[Dict[str, float]]
    ) -> float:
        """Compute aggregate volatility score."""
        if not volatility:
            return 0.3
        vals = list(volatility.values())
        return float(np.mean(vals)) if vals else 0.3

    def _compute_momentum_score(self) -> float:
        """Compute momentum score from price history."""
        scores = []
        for history in self._price_history.values():
            if len(history) < 10:
                continue
            momentum = (history[-1] - history[-10]) / (history[-10] + 1e-8)
            scores.append(momentum)
        return float(np.mean(scores)) if scores else 0.0

    def _compute_risk_score(
        self, portfolio_state: Dict[str, float]
    ) -> float:
        """Compute risk score from portfolio state."""
        exposure = portfolio_state.get("exposure", 0.0)
        leverage = portfolio_state.get("leverage", 0.0)
        drawdown = portfolio_state.get("drawdown", 0.0)
        return min(1.0, 0.3 * exposure + 0.3 * leverage + 0.4 * drawdown)

    def _normalize(self, arr: np.ndarray) -> np.ndarray:
        """Normalize array using configured method."""
        arr = np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)
        if self.config.normalization == "zscore":
            std = np.std(arr)
            if std > 0:
                arr = (arr - np.mean(arr)) / std
        elif self.config.normalization == "minmax":
            arr_min = np.min(arr)
            arr_max = np.max(arr)
            if arr_max > arr_min:
                arr = (arr - arr_min) / (arr_max - arr_min)
        return arr.astype(np.float32)

    def _generate_embedding(self, features: np.ndarray) -> np.ndarray:
        """Generate market embedding via projection."""
        # Simplified: PCA-like projection to embedding_dim
        target_dim = self.config.embedding_dim
        if len(features) <= target_dim:
            result = np.zeros(target_dim, dtype=np.float32)
            result[:len(features)] = features
            return result
        # Simple averaging projection
        step = len(features) // target_dim
        result = np.array([
            np.mean(features[i * step:(i + 1) * step])
            for i in range(target_dim)
        ], dtype=np.float32)
        return result

    def reset(self):
        """Reset encoder state."""
        self._price_history = {}
        self._volume_history = {}

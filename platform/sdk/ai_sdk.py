"""
ICYQuant Platform SDK - AI SDK

Interface for AI model plugins.
Supports ML models, NLP, computer vision, and custom AI agents.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

from . import PluginBase


class AIModelType(str, Enum):
    CLASSIFIER = "classifier"
    REGRESSOR = "regressor"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    NLP = "nlp"
    COMPUTER_VISION = "computer_vision"
    TIME_SERIES = "time_series"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


@dataclass
class AIModelPrediction:
    model_name: str
    model_version: str
    input_data: Dict[str, Any]
    prediction: Any
    confidence: float = 0.0
    prediction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.prediction_id,
            "model": self.model_name,
            "version": self.model_version,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AIModelState:
    name: str
    model_type: AIModelType
    version: str
    is_trained: bool = False
    is_deployed: bool = False
    total_predictions: int = 0
    total_training_samples: int = 0
    accuracy: float = 0.0
    last_training: Optional[datetime] = None
    last_prediction: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.model_type.value,
            "version": self.version,
            "isTrained": self.is_trained,
            "isDeployed": self.is_deployed,
            "totalPredictions": self.total_predictions,
            "accuracy": self.accuracy,
            "lastTraining": self.last_training.isoformat() if self.last_training else None,
        }


class AIModelPlugin(PluginBase):
    """
    Abstract base class for AI model plugins.

    AI models must implement:
    - train(data, labels): Train the model
    - predict(data): Generate predictions
    - evaluate(data, labels): Evaluate model performance
    """

    def __init__(self, model_type: AIModelType = AIModelType.CUSTOM, version: str = "1.0.0"):
        super().__init__()
        self._model_type = model_type
        self._state = AIModelState(
            name=self.__class__.__name__,
            model_type=model_type,
            version=version,
        )
        self._model = None
        self._predictions: List[AIModelPrediction] = []

    @abstractmethod
    def train(self, data: Any, labels: Optional[Any] = None) -> float:
        """Train the model and return accuracy."""
        ...

    @abstractmethod
    def predict(self, data: Any) -> AIModelPrediction:
        """Generate a prediction from input data."""
        ...

    @abstractmethod
    def evaluate(self, data: Any, labels: Any) -> Dict[str, float]:
        """Evaluate model performance."""
        ...

    def get_type(self) -> AIModelType:
        return self._model_type

    def get_state(self) -> AIModelState:
        return self._state

    def initialize(self, config: Dict[str, Any]) -> bool:
        self._config = config
        self._initialized = True
        return True

    def start(self) -> bool:
        self._state.is_deployed = True
        self._running = True
        return True

    def stop(self) -> bool:
        self._state.is_deployed = False
        self._running = False
        return True

    def health_check(self) -> bool:
        return self._initialized and self._state.is_trained

    def get_recent_predictions(self, limit: int = 50) -> List[AIModelPrediction]:
        return self._predictions[-limit:]

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["modelState"] = self._state.to_dict()
        return status


class AISDK:
    """
    SDK for managing AI model plugins.
    """

    def __init__(self):
        self._models: Dict[str, AIModelPlugin] = {}
        self._predictions: List[AIModelPrediction] = []

    def register(self, model: AIModelPlugin) -> str:
        name = model.__class__.__name__
        self._models[name] = model
        return name

    def get_model(self, name: str) -> Optional[AIModelPlugin]:
        return self._models.get(name)

    def list_models(self) -> List[str]:
        return list(self._models.keys())

    def train_model(
        self,
        model_name: str,
        data: Any,
        labels: Optional[Any] = None,
    ) -> Optional[float]:
        model = self._models.get(model_name)
        if not model:
            return None
        return model.train(data, labels)

    def predict(
        self,
        model_name: str,
        data: Any,
    ) -> Optional[AIModelPrediction]:
        model = self._models.get(model_name)
        if not model:
            return None
        prediction = model.predict(data)
        self._predictions.append(prediction)
        return prediction

    def get_recent_predictions(self, limit: int = 50) -> List[AIModelPrediction]:
        return self._predictions[-limit:]

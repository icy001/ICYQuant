"""
ICYQuant Model Metadata - Model metadata schema and management.

Standardized metadata for all ML models in the platform,
enabling consistent model documentation, comparison, and governance.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCategory(Enum):
    """Model categories in quant finance."""

    ALPHA_FACTOR = "alpha_factor"      # alpha factor model
    RETURN_PREDICTION = "return_prediction"
    VOLATILITY_PREDICTION = "volatility_prediction"
    RISK_MODEL = "risk_model"
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    EXECUTION = "execution"
    MARKET_REGIME = "market_regime"
    ANOMALY_DETECTION = "anomaly_detection"
    NLP_SENTIMENT = "nlp_sentiment"
    CUSTOM = "custom"


class ModelRiskTier(Enum):
    """Model risk classification."""

    LOW = "low"         # Informational only
    MEDIUM = "medium"   # Advisory
    HIGH = "high"       # Trading signal
    CRITICAL = "critical"  # Direct execution


@dataclass
class ModelMetadata:
    """Comprehensive metadata for a registered model.

    Captures everything needed for model governance, auditing,
    and regulatory compliance.
    """

    model_id: str = ""
    name: str = ""
    description: str = ""

    # Classification
    category: ModelCategory = ModelCategory.RETURN_PREDICTION
    risk_tier: ModelRiskTier = ModelRiskTier.MEDIUM
    asset_class: str = "equity"
    region: str = "global"

    # Technical
    framework: str = "lightgbm"
    framework_version: str = ""
    model_class: str = ""
    model_type: str = "regressor"

    # Features
    feature_ids: List[str] = field(default_factory=list)
    feature_count: int = 0
    required_market_data: List[str] = field(default_factory=list)

    # Prediction
    prediction_horizon: str = "5d"
    prediction_type: str = "return"  # return, volatility, direction, probability
    prediction_frequency: str = "daily"

    # Training
    dataset_id: Optional[str] = None
    training_date: Optional[datetime] = None
    training_duration_seconds: float = 0.0

    # Performance
    ic: float = 0.0
    rank_ic: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0

    # Governance
    owner: str = ""
    team: str = ""
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    review_date: Optional[datetime] = None
    review_interval_days: int = 90

    # Documentation
    methodology_doc: str = ""
    limitations: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    # Compliance
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage/API."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "category": self.category.value,
            "risk_tier": self.risk_tier.value,
            "framework": self.framework,
            "feature_count": self.feature_count,
            "prediction_horizon": self.prediction_horizon,
            "ic": self.ic,
            "rank_ic": self.rank_ic,
            "sharpe": self.sharpe,
        }

    def to_governance_report(self) -> Dict[str, Any]:
        """Generate a governance/audit report."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "risk_tier": self.risk_tier.value,
            "owner": self.owner,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "review_due": (
                self.review_date.isoformat() if self.review_date
                else (self.created_at.replace(year=self.created_at.year + 1)).isoformat()
            ),
            "performance_ok": self.ic > 0.02,
            "needs_review": (
                self.review_date is not None
                and (datetime.utcnow() - self.review_date).days > self.review_interval_days
            ),
        }

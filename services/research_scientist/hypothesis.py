"""Hypothesis Generation Engine - autonomous hypothesis creation and testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class HypothesisType(Enum):
    """Types of research hypotheses."""

    MARKET = "market"
    FACTOR = "factor"
    STRATEGY = "strategy"
    RELATIONSHIP = "relationship"
    PATTERN = "pattern"
    CAUSAL = "causal"
    PREDICTIVE = "predictive"


class HypothesisStatus(Enum):
    """Hypothesis lifecycle status."""

    PROPOSED = "proposed"
    TESTING = "testing"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    REFINED = "refined"


@dataclass
class Hypothesis:
    """A structured research hypothesis."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    statement: str = ""
    null_statement: str = ""
    hypothesis_type: HypothesisType = HypothesisType.MARKET
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    confidence: float = 0.5
    source: str = ""
    rationale: str = ""
    variables: List[Dict[str, Any]] = field(default_factory=list)
    test_method: str = ""
    evaluation_metrics: List[str] = field(default_factory=list)
    expected_effect: Dict[str, Any] = field(default_factory=dict)
    test_results: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tested_at: Optional[datetime] = None
    refined_from: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "null_statement": self.null_statement,
            "type": self.hypothesis_type.value,
            "status": self.status.value,
            "confidence": self.confidence,
            "source": self.source,
            "rationale": self.rationale,
            "variables": self.variables,
            "test_method": self.test_method,
            "evaluation_metrics": self.evaluation_metrics,
            "expected_effect": self.expected_effect,
            "test_results": self.test_results,
            "created_at": self.created_at.isoformat(),
            "tested_at": self.tested_at.isoformat() if self.tested_at else None,
            "refined_from": self.refined_from,
            "tags": self.tags,
        }


class HypothesisGenerator:
    """Hypothesis Generation Engine.

    Automatically produces structured research hypotheses from:
    - Market observations and questions
    - Existing factor knowledge
    - Strategy performance feedback
    - Data pattern anomalies

    Generates three core hypothesis types:
    1. Market Hypothesis: macro/sector directional predictions
    2. Factor Hypothesis: factor-return relationship conjectures
    3. Strategy Hypothesis: strategy performance predictions

    Each hypothesis includes null hypothesis, variables, test methodology,
    and evaluation metrics for rigorous scientific validation.
    """

    def __init__(self):
        self.hypotheses: Dict[str, Hypothesis] = {}
        self.generation_history: List[Dict[str, Any]] = []
        self.templates: Dict[HypothesisType, List[str]] = {
            HypothesisType.MARKET: [
                "If {condition}, then {asset} will {direction} by {magnitude} over {horizon}",
                "{factor} exceeding {threshold} predicts {asset} returns of {magnitude}",
                "During {regime}, {asset_class} exhibits {behavior} due to {cause}",
            ],
            HypothesisType.FACTOR: [
                "{factor} has {relationship} with future returns when controlling for {controls}",
                "The interaction between {factor_a} and {factor_b} produces excess returns of {magnitude}",
                "{factor} effectiveness is regime-dependent, strongest during {regime}",
            ],
            HypothesisType.STRATEGY: [
                "Combining {signal_a} with {signal_b} improves Sharpe by {magnitude} vs individual signals",
                "{strategy} outperforms benchmark in {condition} with {confidence} confidence",
                "Dynamic weighting of {factors} based on {condition} improves risk-adjusted returns",
            ],
            HypothesisType.RELATIONSHIP: [
                "{variable_x} and {variable_y} exhibit {correlation_type} correlation under {condition}",
                "Changes in {leading_indicator} precede {lagging_indicator} by {lag} periods",
            ],
            HypothesisType.PATTERN: [
                "{pattern_name} pattern in {asset} predicts {direction} movement with {accuracy} accuracy",
                "Recurring {pattern} at {frequency} frequency signals {outcome}",
            ],
            HypothesisType.CAUSAL: [
                "{cause} causes {effect} through {mechanism}, measurable via {metric}",
                "Exogenous shock to {variable} propagates to {asset} returns via {channel}",
            ],
            HypothesisType.PREDICTIVE: [
                "{feature_set} predicts {target} with {metric} > {threshold}",
                "ML model using {features} achieves {performance} on {task}",
            ],
        }

    def generate(self, idea: str) -> Dict[str, Any]:
        """Generate a hypothesis from a research idea.

        This is the primary entry point. Takes a raw idea and
        produces a structured, testable hypothesis.
        """
        hypothesis = self.generate_hypothesis(idea)
        return hypothesis.to_dict()

    def generate_hypothesis(
        self,
        idea: str,
        hypothesis_type: Optional[HypothesisType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Hypothesis:
        """Generate a structured hypothesis from a research idea.

        Args:
            idea: The raw research idea or question.
            hypothesis_type: Optional forced hypothesis type.
            context: Optional contextual information (market data, etc.).

        Returns:
            A fully structured Hypothesis object.
        """
        if hypothesis_type is None:
            hypothesis_type = self._infer_type(idea)

        statement = self._formulate_statement(idea, hypothesis_type)
        null_statement = self._formulate_null(statement, hypothesis_type)
        variables = self._extract_variables(idea, hypothesis_type, context)
        test_method = self._select_test_method(hypothesis_type, variables)
        evaluation_metrics = self._select_metrics(hypothesis_type)
        expected_effect = self._estimate_expected_effect(hypothesis_type, variables)

        hypothesis = Hypothesis(
            statement=statement,
            null_statement=null_statement,
            hypothesis_type=hypothesis_type,
            source=idea,
            rationale=self._generate_rationale(idea, hypothesis_type),
            variables=variables,
            test_method=test_method,
            evaluation_metrics=evaluation_metrics,
            expected_effect=expected_effect,
            confidence=self._initial_confidence(hypothesis_type, variables),
        )

        self.hypotheses[hypothesis.id] = hypothesis
        self.generation_history.append({
            "hypothesis_id": hypothesis.id,
            "idea": idea,
            "type": hypothesis_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return hypothesis

    def _infer_type(self, idea: str) -> HypothesisType:
        """Infer the hypothesis type from the idea text."""
        idea_lower = idea.lower()
        keywords = {
            HypothesisType.MARKET: [
                "market", "sector", "index", "economy", "gdp", "inflation",
                "fed", "central bank", "macro", "bull", "bear", "cycle",
            ],
            HypothesisType.FACTOR: [
                "factor", "momentum", "value", "quality", "size",
                "low vol", "beta", "alpha", "risk premium",
            ],
            HypothesisType.STRATEGY: [
                "strategy", "signal", "entry", "exit", "position",
                "portfolio", "allocation", "hedge", "arbitrage",
            ],
            HypothesisType.RELATIONSHIP: [
                "relationship", "correlation", "causality", "link",
                "connection", "association", "related", "predict",
            ],
            HypothesisType.PATTERN: [
                "pattern", "chart", "technical", "formation",
                "support", "resistance", "trend", "breakout",
            ],
            HypothesisType.CAUSAL: [
                "cause", "effect", "impact", "influence", "drive",
                "lead to", "result in", "due to", "because",
            ],
            HypothesisType.PREDICTIVE: [
                "predict", "forecast", "ml", "machine learning",
                "neural", "deep learning", "model", "train",
            ],
        }

        scores = {}
        for htype, kws in keywords.items():
            scores[htype] = sum(1 for kw in kws if kw in idea_lower)

        if max(scores.values()) == 0:
            return HypothesisType.FACTOR
        return max(scores, key=scores.get)

    def _formulate_statement(self, idea: str, htype: HypothesisType) -> str:
        """Formulate a testable hypothesis statement."""
        templates = self.templates.get(htype, self.templates[HypothesisType.FACTOR])
        template = templates[0]

        # Extract key terms from idea for template filling
        replacements = self._extract_template_vars(idea)
        try:
            statement = template.format(**replacements)
        except (KeyError, ValueError):
            statement = f"{htype.value.upper()}: {idea}"

        return statement

    def _extract_template_vars(self, idea: str) -> Dict[str, str]:
        """Extract variables from idea for template formatting."""
        defaults = {
            "condition": "market stress",
            "asset": "equity",
            "direction": "outperform",
            "magnitude": "2%",
            "horizon": "1 month",
            "factor": "momentum",
            "threshold": "1 standard deviation",
            "relationship": "positive",
            "correlation_type": "positive",
            "regime": "bull market",
            "asset_class": "equities",
            "behavior": "mean reversion",
            "cause": "liquidity expansion",
            "factor_a": "value",
            "factor_b": "momentum",
            "signal_a": "trend",
            "signal_b": "mean_reversion",
            "strategy": "multi-factor",
            "controls": "market beta and sector",
            "variable_x": "VIX",
            "variable_y": "SPX returns",
            "leading_indicator": "yield curve",
            "lagging_indicator": "unemployment",
            "lag": "3",
            "pattern_name": "double bottom",
            "accuracy": "65%",
            "frequency": "daily",
            "outcome": "bullish reversal",
            "effect": "increased volatility",
            "mechanism": "risk aversion",
            "metric": "realized volatility",
            "channel": "correlation breakdown",
            "feature_set": "technical indicators",
            "target": "next-day return",
            "features": "price and volume",
            "performance": "0.65 AUC",
            "task": "direction prediction",
            "confidence": "95%",
            "factors": "momentum and quality",
        }
        return defaults

    def _formulate_null(self, statement: str, htype: HypothesisType) -> str:
        """Formulate the null hypothesis."""
        return f"There is no significant {htype.value} effect: {statement} is false."

    def _extract_variables(
        self,
        idea: str,
        htype: HypothesisType,
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract key variables from the hypothesis."""
        variables = []

        # Independent variables
        variables.append({
            "name": "independent",
            "role": "independent",
            "description": f"Key variable from: {idea[:80]}",
            "data_type": self._guess_data_type(idea, htype),
        })

        # Dependent variables
        if htype in (HypothesisType.MARKET, HypothesisType.FACTOR):
            variables.append({
                "name": "future_returns",
                "role": "dependent",
                "description": "Forward returns over holding period",
                "data_type": "numeric",
                "horizon": "1m",
            })
        elif htype == HypothesisType.STRATEGY:
            variables.append({
                "name": "strategy_pnl",
                "role": "dependent",
                "description": "Strategy profit and loss",
                "data_type": "numeric",
            })

        # Control variables
        variables.append({
            "name": "market_beta",
            "role": "control",
            "description": "Market beta for risk adjustment",
            "data_type": "numeric",
        })

        return variables

    def _guess_data_type(self, idea: str, htype: HypothesisType) -> str:
        if any(kw in idea.lower() for kw in ["sentiment", "news", "social"]):
            return "textual"
        if htype == HypothesisType.PATTERN:
            return "categorical"
        return "numeric"

    def _select_test_method(
        self, htype: HypothesisType, variables: List[Dict[str, Any]]
    ) -> str:
        """Select appropriate statistical test method."""
        methods = {
            HypothesisType.MARKET: "time_series_regression_with_newey_west",
            HypothesisType.FACTOR: "fama_macbeth_regression",
            HypothesisType.STRATEGY: "walk_forward_backtest_with_bootstrap",
            HypothesisType.RELATIONSHIP: "pearson_spearman_correlation",
            HypothesisType.PATTERN: "conditional_probability_analysis",
            HypothesisType.CAUSAL: "granger_causality_test",
            HypothesisType.PREDICTIVE: "cross_validation_with_holdout",
        }
        return methods.get(htype, "statistical_hypothesis_test")

    def _select_metrics(self, htype: HypothesisType) -> List[str]:
        """Select evaluation metrics for the hypothesis."""
        common = ["p_value", "effect_size", "confidence_interval"]
        specific = {
            HypothesisType.MARKET: ["information_coefficient", "hit_rate"],
            HypothesisType.FACTOR: ["t_statistic", "r_squared", "information_ratio"],
            HypothesisType.STRATEGY: ["sharpe_ratio", "max_drawdown", "calmar_ratio"],
            HypothesisType.RELATIONSHIP: ["correlation_coefficient", "r_squared"],
            HypothesisType.PATTERN: ["accuracy", "precision", "recall"],
            HypothesisType.CAUSAL: ["f_statistic", "p_value", "impulse_response"],
            HypothesisType.PREDICTIVE: ["auc_roc", "f1_score", "mse"],
        }
        return common + specific.get(htype, ["custom_metric"])

    def _estimate_expected_effect(
        self, htype: HypothesisType, variables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Estimate expected effect size and direction."""
        return {
            "direction": "positive",
            "magnitude": "moderate",
            "effect_size": "medium",
            "confidence_interval": "[0.1, 0.5]",
        }

    def _generate_rationale(self, idea: str, htype: HypothesisType) -> str:
        return (
            f"This hypothesis was generated from the research idea: '{idea}'. "
            f"Classified as {htype.value} type. "
            f"Testing will determine if the proposed relationship holds."
        )

    def _initial_confidence(
        self, htype: HypothesisType, variables: List[Dict[str, Any]]
    ) -> float:
        # More variables → lower initial confidence
        n_vars = len([v for v in variables if v["role"] != "control"])
        base = 0.6
        penalty = min(n_vars - 1, 4) * 0.1
        return max(0.2, base - penalty)

    def generate_batch(
        self,
        idea: str,
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate multiple hypotheses from a single idea.

        Creates variations across different hypothesis types.
        """
        types = list(HypothesisType)
        results = []
        for i in range(min(count, len(types))):
            hypothesis = self.generate_hypothesis(
                idea=idea,
                hypothesis_type=types[i % len(types)],
            )
            results.append(hypothesis.to_dict())
        return results

    def refine_hypothesis(
        self,
        hypothesis_id: str,
        new_idea: str,
    ) -> Optional[Dict[str, Any]]:
        """Refine an existing hypothesis based on new information."""
        if hypothesis_id not in self.hypotheses:
            return None

        original = self.hypotheses[hypothesis_id]
        refined = self.generate_hypothesis(
            idea=new_idea,
            hypothesis_type=original.hypothesis_type,
        )
        refined.refined_from = hypothesis_id
        refined.statement = (
            f"[REFINED from {hypothesis_id}] {refined.statement}"
        )

        original.status = HypothesisStatus.REFINED
        self.hypotheses[refined.id] = refined

        return refined.to_dict()

    def evaluate_hypothesis(
        self,
        hypothesis_id: str,
        results: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Evaluate a hypothesis with test results."""
        if hypothesis_id not in self.hypotheses:
            return None

        hypothesis = self.hypotheses[hypothesis_id]
        hypothesis.test_results = results
        hypothesis.tested_at = datetime.now(timezone.utc)

        # Determine status based on results
        p_value = results.get("p_value", 0.5)
        if p_value < 0.01:
            hypothesis.status = HypothesisStatus.CONFIRMED
        elif p_value < 0.05:
            hypothesis.status = HypothesisStatus.CONFIRMED
            hypothesis.confidence = 0.8
        elif p_value > 0.10:
            hypothesis.status = HypothesisStatus.REJECTED
        else:
            hypothesis.status = HypothesisStatus.INCONCLUSIVE

        return hypothesis.to_dict()

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific hypothesis by ID."""
        h = self.hypotheses.get(hypothesis_id)
        return h.to_dict() if h else None

    def list_hypotheses(
        self, status: Optional[HypothesisStatus] = None
    ) -> List[Dict[str, Any]]:
        """List hypotheses, optionally filtered by status."""
        result = []
        for h in self.hypotheses.values():
            if status is None or h.status == status:
                result.append({
                    "id": h.id,
                    "statement": h.statement[:100],
                    "type": h.hypothesis_type.value,
                    "status": h.status.value,
                    "confidence": h.confidence,
                })
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of hypothesis generation."""
        total = len(self.hypotheses)
        confirmed = sum(
            1 for h in self.hypotheses.values()
            if h.status == HypothesisStatus.CONFIRMED
        )
        rejected = sum(
            1 for h in self.hypotheses.values()
            if h.status == HypothesisStatus.REJECTED
        )
        return {
            "total_hypotheses": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "pending": total - confirmed - rejected,
            "generation_count": len(self.generation_history),
        }

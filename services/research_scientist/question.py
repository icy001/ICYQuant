"""Research Question Engine - decomposing and analyzing research questions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class QuestionComplexity(Enum):
    """Question complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    MULTI_DOMAIN = "multi_domain"


class QuestionCategory(Enum):
    """Categories of research questions."""

    DESCRIPTIVE = "descriptive"
    COMPARATIVE = "comparative"
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    EXPLORATORY = "exploratory"
    NORMATIVE = "normative"


@dataclass
class AnalyzedQuestion:
    """A fully analyzed research question with decomposition."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    original_question: str = ""
    category: QuestionCategory = QuestionCategory.EXPLORATORY
    complexity: QuestionComplexity = QuestionComplexity.MODERATE
    sub_questions: List[Dict[str, Any]] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    data_requirements: List[Dict[str, Any]] = field(default_factory=list)
    methodology_suggestions: List[str] = field(default_factory=list)
    related_questions: List[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_question": self.original_question,
            "category": self.category.value,
            "complexity": self.complexity.value,
            "sub_questions": self.sub_questions,
            "assumptions": self.assumptions,
            "constraints": self.constraints,
            "data_requirements": self.data_requirements,
            "methodology_suggestions": self.methodology_suggestions,
            "related_questions": self.related_questions,
            "analyzed_at": self.analyzed_at.isoformat(),
            "tags": self.tags,
        }


class ResearchQuestionEngine:
    """Research Question Engine.

    Transforms vague, open-ended research questions into
    structured, verifiable, and testable components.

    Core capabilities:
    1. Question categorization (descriptive, comparative, predictive, causal)
    2. Complexity assessment
    3. Sub-question decomposition
    4. Assumption identification
    5. Data requirement mapping
    6. Methodology suggestion

    This ensures every research project starts with a well-formed
    question that can be rigorously tested.
    """

    def __init__(self):
        self.analyzed_questions: Dict[str, AnalyzedQuestion] = {}
        self.analysis_history: List[Dict[str, Any]] = []
        self.category_keywords: Dict[QuestionCategory, List[str]] = {
            QuestionCategory.DESCRIPTIVE: [
                "what is", "describe", "characterize", "how much",
                "what are", "profile", "summarize",
            ],
            QuestionCategory.COMPARATIVE: [
                "compare", "versus", "vs", "difference", "better",
                "worse", "relative to", "against", "contrast",
            ],
            QuestionCategory.PREDICTIVE: [
                "predict", "forecast", "will", "going to",
                "future", "expect", "project", "anticipate",
            ],
            QuestionCategory.CAUSAL: [
                "why", "cause", "effect", "impact", "influence",
                "drive", "lead to", "result in", "due to",
                "because", "mechanism", "channel",
            ],
            QuestionCategory.EXPLORATORY: [
                "explore", "discover", "find", "identify",
                "search", "investigate", "what patterns",
                "what factors", "what drives",
            ],
            QuestionCategory.NORMATIVE: [
                "should", "optimal", "best", "right",
                "appropriate", "recommend", "allocate",
            ],
        }

    def analyze(self, question: str) -> Dict[str, Any]:
        """Analyze a research question.

        Main entry point for question analysis.
        """
        return self.analyze_question(question).to_dict()

    def analyze_question(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalyzedQuestion:
        """Perform full analysis of a research question.

        Decomposes a broad question into:
        - Category classification
        - Sub-questions for each testable dimension
        - Underlying assumptions
        - Data requirements
        - Suggested methodologies
        """
        category = self._classify_category(question)
        complexity = self._assess_complexity(question)
        sub_questions = self._decompose(question, category, context)
        assumptions = self._extract_assumptions(question)
        constraints = self._identify_constraints(question)
        data_requirements = self._map_data_requirements(question, sub_questions)
        methodology = self._suggest_methodology(category, sub_questions)
        related = self._find_related_questions(question, category)

        analyzed = AnalyzedQuestion(
            original_question=question,
            category=category,
            complexity=complexity,
            sub_questions=sub_questions,
            assumptions=assumptions,
            constraints=constraints,
            data_requirements=data_requirements,
            methodology_suggestions=methodology,
            related_questions=related,
        )

        self.analyzed_questions[analyzed.id] = analyzed
        self.analysis_history.append({
            "id": analyzed.id,
            "question": question[:100],
            "category": category.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return analyzed

    def _classify_category(self, question: str) -> QuestionCategory:
        """Classify the question into a research category."""
        question_lower = question.lower()
        scores = {}
        for cat, keywords in self.category_keywords.items():
            scores[cat] = sum(1 for kw in keywords if kw in question_lower)

        if max(scores.values()) == 0:
            return QuestionCategory.EXPLORATORY
        return max(scores, key=scores.get)

    def _assess_complexity(self, question: str) -> QuestionComplexity:
        """Assess the complexity of the question."""
        question_lower = question.lower()
        complexity_indicators = {
            "and": 1,
            "or": 1,
            "but": 1,
            "however": 1,
            "because": 2,
            "therefore": 2,
            "impact": 1,
            "relationship": 2,
            "interaction": 2,
            "multi": 2,
            "cross": 2,
        }

        score = sum(
            count for kw, count in complexity_indicators.items()
            if kw in question_lower
        )

        # Check for multi-domain indicators
        domain_keywords = [
            "macro", "sector", "factor", "strategy", "risk",
            "portfolio", "execution", "market", "fundamental",
            "technical", "sentiment",
        ]
        domain_count = sum(1 for kw in domain_keywords if kw in question_lower)

        total = score + domain_count

        if total >= 5 or domain_count >= 3:
            return QuestionComplexity.MULTI_DOMAIN
        elif total >= 3:
            return QuestionComplexity.COMPLEX
        elif total >= 1:
            return QuestionComplexity.MODERATE
        return QuestionComplexity.SIMPLE

    def _decompose(
        self,
        question: str,
        category: QuestionCategory,
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Decompose a question into testable sub-questions."""
        sub_questions = []
        decomposition_frameworks = {
            QuestionCategory.DESCRIPTIVE: [
                ("measurement", "What is the magnitude of {topic}?"),
                ("distribution", "How is {topic} distributed across {dimension}?"),
                ("trend", "How has {topic} changed over time?"),
                ("segmentation", "How does {topic} vary by {segment}?"),
            ],
            QuestionCategory.COMPARATIVE: [
                ("baseline", "What is the baseline performance of {topic}?"),
                ("difference", "What is the difference between {a} and {b}?"),
                ("significance", "Is the difference statistically significant?"),
                ("persistence", "Does the difference persist across regimes?"),
            ],
            QuestionCategory.PREDICTIVE: [
                ("features", "What features best predict {target}?"),
                ("model", "What model architecture is optimal for predicting {target}?"),
                ("accuracy", "What prediction accuracy can be achieved?"),
                ("stability", "How stable are predictions over time?"),
            ],
            QuestionCategory.CAUSAL: [
                ("mechanism", "What is the causal mechanism linking {cause} to {effect}?"),
                ("direction", "What is the direction of causality?"),
                ("magnitude", "What is the magnitude of the causal effect?"),
                ("confounding", "What confounding variables exist?"),
                ("heterogeneity", "Does the effect vary across subgroups?"),
            ],
            QuestionCategory.EXPLORATORY: [
                ("patterns", "What patterns exist in {topic}?"),
                ("anomalies", "What anomalies or outliers exist?"),
                ("clusters", "What natural groupings exist in the data?"),
                ("relationships", "What relationships exist between variables?"),
            ],
            QuestionCategory.NORMATIVE: [
                ("objectives", "What are the optimization objectives?"),
                ("constraints", "What constraints must be satisfied?"),
                ("tradeoffs", "What are the key trade-offs?"),
                ("robustness", "How robust is the optimal solution?"),
            ],
        }

        framework = decomposition_frameworks.get(
            category, decomposition_frameworks[QuestionCategory.EXPLORATORY]
        )

        for dim_id, template in framework:
            sub_questions.append({
                "id": dim_id,
                "dimension": dim_id,
                "question": template.format(
                    topic=question[:60],
                    dimension="time",
                    segment="market_cap",
                    a="treatment",
                    b="control",
                    target="returns",
                    cause="factor",
                    effect="returns",
                ),
                "type": category.value,
                "priority": "high",
            })

        return sub_questions

    def _extract_assumptions(self, question: str) -> List[str]:
        """Extract implicit assumptions from the question."""
        assumptions = [
            "Markets are sufficiently efficient for the question to be meaningful",
            "Required data is available and of sufficient quality",
            "The relationship, if it exists, is measurable",
            "Historical patterns have some predictive value",
        ]

        question_lower = question.lower()
        if "predict" in question_lower or "forecast" in question_lower:
            assumptions.append("Past relationships will persist in the future")
        if "factor" in question_lower:
            assumptions.append("Factor exposures can be accurately measured")
        if "strategy" in question_lower:
            assumptions.append("Transaction costs are manageable")
        if "risk" in question_lower:
            assumptions.append("Risk can be adequately modeled and quantified")

        return assumptions

    def _identify_constraints(self, question: str) -> List[str]:
        """Identify practical constraints for the research."""
        return [
            "Data availability and quality",
            "Computational resources",
            "Time horizon for analysis",
            "Statistical significance requirements",
            "Out-of-sample validation requirements",
        ]

    def _map_data_requirements(
        self, question: str, sub_questions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Map data requirements for each sub-question."""
        data_requirements = []
        question_lower = question.lower()

        base_requirements = [
            {
                "type": "market_data",
                "fields": ["price", "volume", "returns"],
                "frequency": "daily",
                "required": any(
                    kw in question_lower
                    for kw in ["price", "return", "market", "stock", "equity"]
                ),
            },
            {
                "type": "fundamental_data",
                "fields": ["pe_ratio", "pb_ratio", "roe", "earnings"],
                "frequency": "quarterly",
                "required": any(
                    kw in question_lower
                    for kw in ["fundamental", "valuation", "earnings", "financial"]
                ),
            },
            {
                "type": "macro_data",
                "fields": ["gdp", "inflation", "interest_rate", "unemployment"],
                "frequency": "monthly",
                "required": any(
                    kw in question_lower
                    for kw in ["macro", "economy", "gdp", "inflation", "fed"]
                ),
            },
            {
                "type": "alternative_data",
                "fields": ["sentiment", "news", "social_media"],
                "frequency": "daily",
                "required": any(
                    kw in question_lower
                    for kw in ["sentiment", "news", "social", "alternative"]
                ),
            },
        ]

        for req in base_requirements:
            if req["required"] or len(data_requirements) < 2:
                data_requirements.append(req)

        return data_requirements

    def _suggest_methodology(
        self, category: QuestionCategory, sub_questions: List[Dict[str, Any]]
    ) -> List[str]:
        """Suggest appropriate research methodologies."""
        methodologies = {
            QuestionCategory.DESCRIPTIVE: [
                "Exploratory Data Analysis (EDA)",
                "Summary statistics and visualization",
                "Distribution fitting and testing",
            ],
            QuestionCategory.COMPARATIVE: [
                "Two-sample hypothesis testing",
                "ANOVA / MANOVA",
                "Effect size estimation (Cohen's d)",
            ],
            QuestionCategory.PREDICTIVE: [
                "Cross-validated machine learning",
                "Time series cross-validation",
                "Feature importance analysis",
            ],
            QuestionCategory.CAUSAL: [
                "Granger causality testing",
                "Instrumental variables",
                "Difference-in-differences",
                "Regression discontinuity",
            ],
            QuestionCategory.EXPLORATORY: [
                "Clustering analysis",
                "Dimensionality reduction (PCA/t-SNE)",
                "Association rule mining",
            ],
            QuestionCategory.NORMATIVE: [
                "Convex optimization",
                "Portfolio optimization (Markowitz)",
                "Dynamic programming",
                "Reinforcement learning",
            ],
        }

        return methodologies.get(category, ["General statistical analysis"])

    def _find_related_questions(
        self, question: str, category: QuestionCategory
    ) -> List[str]:
        """Suggest related research questions to explore."""
        related = []
        question_lower = question.lower()

        related_templates = {
            "factor": [
                "How stable is this factor across market regimes?",
                "What is the optimal combination of related factors?",
            ],
            "momentum": [
                "How does momentum interact with volatility?",
                "What is the optimal lookback period for momentum?",
            ],
            "value": [
                "How does value perform in different interest rate environments?",
                "What metrics best capture value in the current market?",
            ],
            "risk": [
                "What is the tail risk profile of this approach?",
                "How does correlation structure change during stress?",
            ],
        }

        for keyword, questions in related_templates.items():
            if keyword in question_lower:
                related.extend(questions)

        if not related:
            related = [
                "How robust are these findings to different market regimes?",
                "What is the capacity constraint of this approach?",
            ]

        return related[:3]

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a previous question analysis."""
        a = self.analyzed_questions.get(analysis_id)
        return a.to_dict() if a else None

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of question analyses."""
        categories = {}
        for a in self.analyzed_questions.values():
            cat = a.category.value
            categories[cat] = categories.get(cat, 0) + 1

        complexities = {}
        for a in self.analyzed_questions.values():
            comp = a.complexity.value
            complexities[comp] = complexities.get(comp, 0) + 1

        return {
            "total_analyzed": len(self.analyzed_questions),
            "by_category": categories,
            "by_complexity": complexities,
        }

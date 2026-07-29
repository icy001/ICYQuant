"""AI Research Scientist Agent - autonomous quant research agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ResearchDomain(Enum):
    """Research focus domains."""

    MACRO = "macro"
    SECTOR = "sector"
    FACTOR = "factor"
    STRATEGY = "strategy"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    EXECUTION = "execution"
    ALTERNATIVE = "alternative"
    CROSS_ASSET = "cross_asset"
    MARKET_MICROSTRUCTURE = "market_microstructure"


class ResearchStatus(Enum):
    """Research project lifecycle status."""

    PROPOSED = "proposed"
    HYPOTHESIS_FORMED = "hypothesis_formed"
    EXPERIMENTING = "experimenting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    PUBLISHED = "published"
    DEPLOYED = "deployed"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ResearchPriority(Enum):
    """Research priority levels."""

    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    EXPLORATORY = 1


@dataclass
class ResearchQuestion:
    """Structured research question."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    question: str = ""
    domain: ResearchDomain = ResearchDomain.FACTOR
    priority: ResearchPriority = ResearchPriority.MEDIUM
    sub_questions: List[Dict[str, Any]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "domain": self.domain.value,
            "priority": self.priority.value,
            "sub_questions": self.sub_questions,
            "context": self.context,
            "expected_outcome": self.expected_outcome,
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
        }


@dataclass
class ResearchProject:
    """Full research project tracking."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    question: Optional[ResearchQuestion] = None
    status: ResearchStatus = ResearchStatus.PROPOSED
    domain: ResearchDomain = ResearchDomain.FACTOR
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    discoveries: List[Dict[str, Any]] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    report_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question.to_dict() if self.question else None,
            "status": self.status.value,
            "domain": self.domain.value,
            "hypotheses": self.hypotheses,
            "experiments": self.experiments,
            "discoveries": self.discoveries,
            "results": self.results,
            "report_id": self.report_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat(),
            "notes": self.notes,
        }


class ResearchScientistAgent:
    """AI Research Scientist Agent.

    Models the role of a quantitative research scientist:
    - Receives market questions and research ideas
    - Decomposes into structured research questions
    - Designs research direction and methodology
    - Plans experiments to test hypotheses
    - Oversees the full research lifecycle

    This agent serves as the "brain" of the AI Quant Research Lab,
    coordinating hypothesis generation, experimentation, discovery,
    and ultimately producing deployable alpha.
    """

    def __init__(
        self,
        name: str = "ResearchScientist",
        domain: ResearchDomain = ResearchDomain.FACTOR,
    ):
        self.name = name
        self.domain = domain
        self.active_projects: Dict[str, ResearchProject] = {}
        self.completed_projects: Dict[str, ResearchProject] = {}
        self.research_queue: List[ResearchQuestion] = []
        self.research_history: List[Dict[str, Any]] = []

    def research(self, question: str) -> Dict[str, Any]:
        """Main entry point: receive a question and initiate research.

        This is the primary method that kickstarts the autonomous
        research loop: question → hypothesis → experiment → discovery.
        """
        return self.initiate_research(question)

    def initiate_research(self, question_text: str) -> Dict[str, Any]:
        """Initiate a new research project from a question."""
        project = ResearchProject(
            title=question_text,
            status=ResearchStatus.PROPOSED,
            started_at=datetime.now(timezone.utc),
        )
        project.question = ResearchQuestion(
            question=question_text,
        )
        self.active_projects[project.id] = project
        self.research_history.append({
            "action": "initiated",
            "project_id": project.id,
            "question": question_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "project_id": project.id,
            "status": project.status.value,
            "question": question_text,
            "message": f"Research project initiated: {question_text}",
        }

    def decompose_question(
        self, project_id: str, question_text: str
    ) -> Dict[str, Any]:
        """Decompose a broad question into verifiable sub-questions.

        Transforms vague market questions into testable research
        components. E.g., "Why are AI stocks rising?" becomes:
        - GPU revenue trends
        - HBM pricing dynamics
        - AI CapEx cycle analysis
        - Gross margin expansion patterns
        """
        if project_id not in self.active_projects:
            return {"error": f"Project {project_id} not found"}

        project = self.active_projects[project_id]
        sub_questions = self._generate_sub_questions(question_text, project.domain)
        project.question.sub_questions = sub_questions
        project.question.question = question_text
        project.status = ResearchStatus.HYPOTHESIS_FORMED
        project.updated_at = datetime.now(timezone.utc)

        self.research_history.append({
            "action": "decomposed",
            "project_id": project_id,
            "sub_questions_count": len(sub_questions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "project_id": project_id,
            "main_question": question_text,
            "sub_questions": sub_questions,
            "count": len(sub_questions),
            "status": project.status.value,
        }

    def _generate_sub_questions(
        self, question: str, domain: ResearchDomain
    ) -> List[Dict[str, Any]]:
        """Generate structured sub-questions from a broad research question."""
        sub_questions = []
        frameworks = {
            ResearchDomain.MACRO: [
                "monetary_policy", "fiscal_policy", "growth_cycle",
                "inflation", "employment", "global_trade",
            ],
            ResearchDomain.SECTOR: [
                "revenue_trends", "margin_analysis", "capex_cycle",
                "competitive_landscape", "regulatory_impact", "supply_chain",
            ],
            ResearchDomain.FACTOR: [
                "momentum", "value", "quality", "low_volatility",
                "size", "growth",
            ],
            ResearchDomain.STRATEGY: [
                "entry_signal", "exit_signal", "position_sizing",
                "risk_management", "holding_period", "universe_selection",
            ],
            ResearchDomain.RISK: [
                "volatility", "correlation", "tail_risk",
                "liquidity", "concentration", "drawdown",
            ],
            ResearchDomain.PORTFOLIO: [
                "allocation", "rebalancing", "diversification",
                "currency_exposure", "sector_exposure", "factor_exposure",
            ],
            ResearchDomain.EXECUTION: [
                "market_impact", "timing", "venue_selection",
                "order_type", "slippage", "fill_rate",
            ],
            ResearchDomain.ALTERNATIVE: [
                "sentiment", "satellite", "web_scraping",
                "social_media", "supply_chain_data", "credit_card_data",
            ],
            ResearchDomain.CROSS_ASSET: [
                "equity_fixed_income", "commodity_equity",
                "fx_equity", "volatility_spillover", "cross_border_flows",
            ],
            ResearchDomain.MARKET_MICROSTRUCTURE: [
                "order_book", "spread", "depth",
                "high_frequency", "latency", "market_making",
            ],
        }

        dimensions = frameworks.get(domain, frameworks[ResearchDomain.FACTOR])
        for i, dim in enumerate(dimensions):
            sub_questions.append({
                "id": f"{dim}_{i}",
                "dimension": dim,
                "question": f"[{dim}] {self._dimension_question(dim, question)}",
                "metrics": self._dimension_metrics(dim),
                "data_requirements": self._dimension_data(dim),
            })

        return sub_questions

    def _dimension_question(self, dim: str, context: str) -> str:
        return f"How does {dim.replace('_', ' ')} relate to: {context}?"

    def _dimension_metrics(self, dim: str) -> List[str]:
        metric_map = {
            "momentum": ["returns_3m", "returns_6m", "returns_12m"],
            "value": ["pe_ratio", "pb_ratio", "ev_ebitda"],
            "quality": ["roe", "debt_equity", "earnings_stability"],
            "volatility": ["realized_vol", "implied_vol", "beta"],
            "liquidity": ["bid_ask_spread", "volume", "turnover"],
        }
        return metric_map.get(dim, ["custom_metric"])

    def _dimension_data(self, dim: str) -> List[str]:
        data_map = {
            "momentum": ["price_history", "volume_history"],
            "value": ["financial_statements", "market_data"],
            "sentiment": ["news_feed", "social_media"],
            "volatility": ["option_chain", "price_history"],
        }
        return data_map.get(dim, ["market_data"])

    def update_project_status(
        self, project_id: str, status: ResearchStatus
    ) -> Dict[str, Any]:
        """Update the status of a research project."""
        if project_id not in self.active_projects:
            return {"error": f"Project {project_id} not found"}

        project = self.active_projects[project_id]
        project.status = status
        project.updated_at = datetime.now(timezone.utc)

        if status in (ResearchStatus.COMPLETED, ResearchStatus.PUBLISHED,
                      ResearchStatus.DEPLOYED):
            project.completed_at = datetime.now(timezone.utc)
            self.completed_projects[project_id] = project
            del self.active_projects[project_id]

        if status == ResearchStatus.REJECTED:
            self.completed_projects[project_id] = project
            del self.active_projects[project_id]

        return {
            "project_id": project_id,
            "status": status.value,
            "updated_at": project.updated_at.isoformat(),
        }

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """List all active research projects."""
        return [
            {"id": pid, "title": p.title, "status": p.status.value,
             "domain": p.domain.value, "started_at": p.started_at.isoformat() if p.started_at else None}
            for pid, p in self.active_projects.items()
        ]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific research project."""
        project = (
            self.active_projects.get(project_id)
            or self.completed_projects.get(project_id)
        )
        if not project:
            return None
        return project.to_dict()

    def get_research_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all research activity."""
        total = len(self.completed_projects) + len(self.active_projects)
        active = len(self.active_projects)
        completed = len(self.completed_projects)
        deployed = sum(
            1 for p in self.completed_projects.values()
            if p.status == ResearchStatus.DEPLOYED
        )
        rejected = sum(
            1 for p in self.completed_projects.values()
            if p.status == ResearchStatus.REJECTED
        )
        return {
            "total_projects": total,
            "active": active,
            "completed": completed,
            "deployed": deployed,
            "rejected": rejected,
            "history_entries": len(self.research_history),
        }

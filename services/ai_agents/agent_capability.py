"""
ICYQuant Agent Capability — dynamic capability registry for agents.

Defines agent capabilities as a structured, discoverable taxonomy
that enables the task router to match tasks to the right agents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CapabilityDomain(str, Enum):
    RESEARCH = "research"
    FACTOR = "factor"
    STRATEGY = "strategy"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    EXECUTION = "execution"
    REVIEW = "review"
    COORDINATION = "coordination"


@dataclass
class Capability:
    """A named capability that an agent can provide."""
    name: str
    domain: CapabilityDomain
    description: str = ""
    required_tools: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Pre-defined Capability Catalog ──

CAPABILITY_CATALOG: dict[str, Capability] = {
    # Research
    "document_search": Capability(
        name="document_search",
        domain=CapabilityDomain.RESEARCH,
        description="Search knowledge base and research documents",
        required_tools=["knowledge_search", "semantic_retrieval"],
    ),
    "market_analysis": Capability(
        name="market_analysis",
        domain=CapabilityDomain.RESEARCH,
        description="Analyze market conditions and trends",
        required_tools=["market_data", "historical_data"],
    ),
    "evidence_collection": Capability(
        name="evidence_collection",
        domain=CapabilityDomain.RESEARCH,
        description="Gather evidence for hypotheses",
        required_tools=["evidence_engine", "citation_manager"],
    ),

    # Factor
    "factor_generation": Capability(
        name="factor_generation",
        domain=CapabilityDomain.FACTOR,
        description="Generate and discover alpha factors",
        required_tools=["data_lake", "feature_store"],
    ),
    "factor_testing": Capability(
        name="factor_testing",
        domain=CapabilityDomain.FACTOR,
        description="Test factor performance and IC analysis",
        required_tools=["backtest_engine", "statistical_tests"],
    ),
    "factor_analysis": Capability(
        name="factor_analysis",
        domain=CapabilityDomain.FACTOR,
        description="Analyze factor behavior and decay",
        required_tools=["factor_analyzer"],
    ),

    # Strategy
    "strategy_generation": Capability(
        name="strategy_generation",
        domain=CapabilityDomain.STRATEGY,
        description="Generate trading strategy candidates",
        required_tools=["strategy_engine"],
    ),
    "backtest_request": Capability(
        name="backtest_request",
        domain=CapabilityDomain.STRATEGY,
        description="Run strategy backtests",
        required_tools=["backtest_engine"],
    ),
    "strategy_review": Capability(
        name="strategy_review",
        domain=CapabilityDomain.STRATEGY,
        description="Review and critique strategies",
        required_tools=["review_engine"],
    ),

    # Risk
    "risk_analysis": Capability(
        name="risk_analysis",
        domain=CapabilityDomain.RISK,
        description="Analyze portfolio and strategy risk",
        required_tools=["risk_engine"],
    ),
    "stress_test": Capability(
        name="stress_test",
        domain=CapabilityDomain.RISK,
        description="Run stress test scenarios",
        required_tools=["risk_engine", "scenario_engine"],
    ),
    "exposure_analysis": Capability(
        name="exposure_analysis",
        domain=CapabilityDomain.RISK,
        description="Analyze factor and market exposures",
        required_tools=["risk_engine"],
    ),

    # Portfolio
    "portfolio_optimization": Capability(
        name="portfolio_optimization",
        domain=CapabilityDomain.PORTFOLIO,
        description="Optimize portfolio weights",
        required_tools=["optimization_engine"],
    ),
    "allocation_analysis": Capability(
        name="allocation_analysis",
        domain=CapabilityDomain.PORTFOLIO,
        description="Analyze asset allocation",
        required_tools=["portfolio_analyzer"],
    ),

    # Review
    "quality_review": Capability(
        name="quality_review",
        domain=CapabilityDomain.REVIEW,
        description="Review research quality and methodology",
        required_tools=["review_engine"],
    ),
    "bias_detection": Capability(
        name="bias_detection",
        domain=CapabilityDomain.REVIEW,
        description="Detect bias in analysis and conclusions",
        required_tools=["bias_detector"],
    ),

    # Coordination
    "task_planning": Capability(
        name="task_planning",
        domain=CapabilityDomain.COORDINATION,
        description="Decompose requests into task plans",
        required_tools=["task_planner"],
    ),
    "agent_orchestration": Capability(
        name="agent_orchestration",
        domain=CapabilityDomain.COORDINATION,
        description="Coordinate multi-agent workflows",
        required_tools=["orchestrator"],
    ),
}


def get_capability(name: str) -> Optional[Capability]:
    """Look up a capability by name."""
    return CAPABILITY_CATALOG.get(name)


def list_capabilities_by_domain(domain: CapabilityDomain) -> list[Capability]:
    """List all capabilities in a domain."""
    return [c for c in CAPABILITY_CATALOG.values() if c.domain == domain]


def list_all_capabilities() -> list[Capability]:
    """List all registered capabilities."""
    return list(CAPABILITY_CATALOG.values())

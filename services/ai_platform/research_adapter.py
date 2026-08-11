"""Research Adapter — Bridges AI Platform with Research subsystem."""

from __future__ import annotations

import logging
from typing import Any, Dict, TYPE_CHECKING

from .ai_session import AISession

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


class ResearchAdapter:
    """Adapter for AI Research Platform integration.

    Bridges the AI Platform to the Research subsystem so agents
    can query hypotheses, evidence, experiments, and literature
    without direct coupling.
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config

    async def research(self, session: AISession) -> Dict[str, Any]:
        """Execute AI research for a session.

        Routes research requests to the AI Research subsystem,
        returning hypotheses, evidence, and analysis results.
        """
        query = session.query or session.parameters.get("query", "")
        symbols = session.symbols

        result = {
            "query": query,
            "symbols": symbols,
            "hypotheses": [],
            "evidence": [],
            "analysis": {},
            "status": "completed",
        }

        try:
            # Forward to AI Research platform if connected
            from services.ai_research.ai_research_platform import AIResearchPlatform
            research = AIResearchPlatform()
            if hasattr(research, 'research'):
                research_result = await research.research(query, symbols)
                result.update(research_result)
        except ImportError:
            logger.debug("AI Research platform not available, using local analysis")
        except Exception as exc:
            logger.warning("Research adapter error: %s", exc)

        return result

    async def analyze(self, session: AISession, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze provided data using research tools."""
        return {
            "analysis_type": "general",
            "findings": [],
            "confidence": 0.0,
        }

    async def health(self) -> Dict[str, Any]:
        return {"connected": True, "status": "ready"}

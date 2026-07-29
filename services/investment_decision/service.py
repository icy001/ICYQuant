from typing import Any, Dict

from .thesis import InvestmentThesisGenerator
from .opportunity import OpportunityEvaluationEngine
from .committee import AIInvestmentCommittee
from .bull_agent import BullCaseAgent
from .bear_agent import BearCaseAgent
from .conviction import ConvictionScoreEngine
from .decision import InvestmentDecisionEngine
from .explanation import DecisionExplanationEngine
from .review import DecisionReviewEngine
from .memory import InvestmentDecisionMemory


class InvestmentDecisionService:
    """Investment Decision Service - orchestrates the full autonomous investment decision loop."""

    def __init__(self, committee):
        self.committee = committee
        self.thesis_generator = InvestmentThesisGenerator()
        self.opportunity_evaluator = OpportunityEvaluationEngine()
        self.bull_agent = BullCaseAgent()
        self.bear_agent = BearCaseAgent()
        self.conviction_engine = ConvictionScoreEngine()
        self.decision_engine = InvestmentDecisionEngine()
        self.explanation_engine = DecisionExplanationEngine()
        self.review_engine = DecisionReviewEngine()
        self.memory = InvestmentDecisionMemory()

    def decide(self, thesis):
        """Make an investment decision by discussing a thesis with the committee.

        Args:
            thesis: The investment thesis to decide on.

        Returns:
            Dict containing the committee decision.
        """
        return self.committee.discuss(thesis)

    def run_full_loop(self, opportunity) -> Dict[str, Any]:
        """Run the complete autonomous investment decision loop.

        Steps:
        1. Investment Thesis Generation
        2. Opportunity Evaluation
        3. Bull Case Analysis
        4. Bear Case Analysis
        5. Committee Discussion
        6. Conviction Scoring
        7. Investment Decision
        8. Decision Explanation
        9. Decision Review (if outcome data available)
        10. Memory Recording
        """
        # Step 1: Generate investment thesis
        thesis = self.thesis_generator.generate(opportunity)

        # Step 2: Evaluate opportunity
        evaluation = self.opportunity_evaluator.evaluate(opportunity)

        # Step 3: Bull case analysis
        bull_case = self.bull_agent.analyze(opportunity)

        # Step 4: Bear case analysis
        bear_case = self.bear_agent.analyze(opportunity)

        # Step 5: Committee discussion
        committee_result = self.committee.discuss(thesis)

        # Step 6: Conviction scoring
        conviction = self.conviction_engine.score({
            "bull_case": bull_case,
            "bear_case": bear_case,
            "votes": committee_result.get("decision", {}).get("votes", []),
        })

        # Step 7: Investment decision
        decision = self.decision_engine.decide(conviction)

        # Step 8: Decision explanation
        explanation = self.explanation_engine.explain({
            "thesis": thesis.get("thesis", {}),
            "bull_case": bull_case,
            "bear_case": bear_case,
            "decision": decision.get("decision", {}),
            "votes": committee_result.get("decision", {}).get("votes", []),
        })

        # Step 9: Save to memory
        self.memory.save(decision)

        return {
            "thesis": thesis,
            "evaluation": evaluation,
            "bull_case": bull_case,
            "bear_case": bear_case,
            "committee": committee_result,
            "conviction": conviction,
            "decision": decision,
            "explanation": explanation,
            "status": "COMPLETED",
        }

    def review_decision(self, decision_data: Dict[str, Any]) -> Dict[str, Any]:
        """Review a past decision outcome for learning.

        Args:
            decision_data: Dict containing decision and outcome data.

        Returns:
            Dict containing the review result.
        """
        review = self.review_engine.review(decision_data)
        self.memory.save(decision_data)
        return review

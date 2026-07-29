from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Rank(str, Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"
    WATCHLIST = "WATCHLIST"
    REJECT = "REJECT"


@dataclass
class OpportunityScore:
    symbol: str
    alpha_potential: float = 0.0  # 0-100
    risk_reward: float = 0.0  # 0-100
    conviction: float = 0.0  # 0-100
    liquidity: float = 0.0  # 0-100
    composite: float = 0.0  # 0-100
    rank: Rank = Rank.WATCHLIST


@dataclass
class OpportunityRanking:
    ranking_id: str
    opportunities: List[OpportunityScore] = field(default_factory=list)
    total_opportunities: int = 0
    actionable_count: int = 0
    generated_at: str = ""


class OpportunityRankingEngine:
    """Opportunity Ranking Engine - ranks investment opportunities by multiple factors."""

    def __init__(self):
        self.rankings: List[OpportunityRanking] = []
        self.rank_count = 0

    def rank(self, opportunities):
        """Rank investment opportunities.

        Args:
            opportunities: List of opportunities (str, dict, list, or OpportunityRanking).

        Returns:
            Dict containing ranked opportunities.
        """
        if isinstance(opportunities, OpportunityRanking):
            return self._process_ranking(opportunities)
        if isinstance(opportunities, list):
            return self._rank_list(opportunities)
        if isinstance(opportunities, dict):
            return self._rank_dict(opportunities)
        return {"ranking": opportunities}

    def _process_ranking(self, ranking: OpportunityRanking) -> dict:
        self.rankings.append(ranking)
        return self._to_dict(ranking)

    def _rank_list(self, opps: list) -> dict:
        self.rank_count += 1
        scores = []

        for opp in opps:
            if isinstance(opp, OpportunityScore):
                scores.append(opp)
            elif isinstance(opp, dict):
                scores.append(self._score_opportunity(opp))
            else:
                scores.append(OpportunityScore(symbol=str(opp)))

        # Sort by composite score descending
        scores.sort(key=lambda s: s.composite, reverse=True)

        # Assign tiers
        for i, s in enumerate(scores):
            if s.composite >= 80:
                s.rank = Rank.TIER_1
            elif s.composite >= 65:
                s.rank = Rank.TIER_2
            elif s.composite >= 50:
                s.rank = Rank.TIER_3
            elif s.composite >= 30:
                s.rank = Rank.TIER_4
            else:
                s.rank = Rank.REJECT

        actionable = sum(1 for s in scores if s.rank in (Rank.TIER_1, Rank.TIER_2))

        ranking = OpportunityRanking(
            ranking_id=f"RANK_{self.rank_count:04d}",
            opportunities=scores,
            total_opportunities=len(scores),
            actionable_count=actionable,
        )
        self.rankings.append(ranking)
        return self._to_dict(ranking)

    def _rank_dict(self, data: dict) -> dict:
        opps = data.get("opportunities", [data])
        return self._rank_list(opps)

    def _score_opportunity(self, opp: dict) -> OpportunityScore:
        alpha = opp.get("alpha_potential", opp.get("alpha", 50))
        risk_reward = opp.get("risk_reward", opp.get("rr_ratio", 50))
        conviction = opp.get("conviction", opp.get("conviction_score", 50))
        liquidity = opp.get("liquidity", opp.get("liquidity_score", 50))

        # Weighted composite
        composite = (
            float(alpha) * 0.30
            + float(risk_reward) * 0.25
            + float(conviction) * 0.25
            + float(liquidity) * 0.20
        )

        return OpportunityScore(
            symbol=opp.get("symbol", "UNKNOWN"),
            alpha_potential=round(float(alpha), 1),
            risk_reward=round(float(risk_reward), 1),
            conviction=round(float(conviction), 1),
            liquidity=round(float(liquidity), 1),
            composite=round(composite, 1),
        )

    def _to_dict(self, ranking: OpportunityRanking) -> dict:
        return {
            "ranking": {
                "ranking_id": ranking.ranking_id,
                "opportunities": [
                    {
                        "symbol": s.symbol,
                        "alpha_potential": s.alpha_potential,
                        "risk_reward": s.risk_reward,
                        "conviction": s.conviction,
                        "liquidity": s.liquidity,
                        "composite": s.composite,
                        "rank": s.rank.value,
                    }
                    for s in ranking.opportunities
                ],
                "total_opportunities": ranking.total_opportunities,
                "actionable_count": ranking.actionable_count,
            }
        }

    def get_top_opportunities(self, n: int = 3) -> List[OpportunityScore]:
        """Get top N ranked opportunities."""
        if not self.rankings:
            return []
        return self.rankings[-1].opportunities[:n]

    def get_by_tier(self, tier: Rank) -> List[OpportunityScore]:
        """Get opportunities filtered by tier."""
        if not self.rankings:
            return []
        return [s for s in self.rankings[-1].opportunities if s.rank == tier]

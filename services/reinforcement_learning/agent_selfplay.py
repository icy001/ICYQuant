"""Agent Self-Play — multi-agent competitive learning for RL trading.

Simulates multiple AI traders competing in the same market, each with
different strategies. Through competition, stronger policies emerge
that can handle diverse market participants.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import copy
import random

import numpy as np

from .environment import RLTradingEnvironment, EnvironmentConfig, MarketState
from .policy_network import PolicyNetwork, PolicyConfig
from .action_space import ActionSpace, DiscreteActionSpace


class AgentStrategy(Enum):
    """Types of trading strategies for self-play agents."""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MARKET_MAKING = "market_making"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    ARBITRAGE = "arbitrage"
    RL_TRAINED = "rl_trained"
    RANDOM = "random"
    BUY_HOLD = "buy_hold"


@dataclass
class SelfPlayConfig:
    """Configuration for self-play training."""

    # Agents
    n_agents: int = 4
    agent_strategies: List[AgentStrategy] = field(default_factory=lambda: [
        AgentStrategy.TREND_FOLLOWING,
        AgentStrategy.MEAN_REVERSION,
        AgentStrategy.MARKET_MAKING,
        AgentStrategy.MOMENTUM,
    ])

    # Competition
    n_rounds: int = 100
    episodes_per_round: int = 10
    tournament_size: int = 2

    # ELO rating
    initial_elo: float = 1500.0
    elo_k_factor: float = 32.0

    # Policy update
    update_target_interval: int = 10
    use_opponent_pool: bool = True
    opponent_pool_size: int = 5

    # Environment
    env_config: Optional[EnvironmentConfig] = None

    seed: int = 42


@dataclass
class SelfPlayAgent:
    """An agent in the self-play ecosystem."""

    agent_id: str
    strategy: AgentStrategy
    policy: Optional[PolicyNetwork] = None
    elo_rating: float = 1500.0
    win_count: int = 0
    loss_count: int = 0
    total_reward: float = 0.0
    history: List[Dict[str, Any]] = field(default_factory=list)

    def win_rate(self) -> float:
        total = self.win_count + self.loss_count
        return self.win_count / total if total > 0 else 0.0


@dataclass
class CompetitionResult:
    """Result of a self-play competition round."""

    round_id: int
    rankings: List[Tuple[str, float, float]]  # (agent_id, score, elo_change)
    match_results: List[Dict[str, Any]]
    best_agent_id: str
    best_score: float
    elo_standings: Dict[str, float]


class SelfPlayManager:
    """Manages multi-agent self-play training.

    Creates a competitive ecosystem where agents with different
    strategies compete. Uses ELO ratings to track performance
    and maintains an opponent pool for robust training.

    Usage:
        manager = SelfPlayManager(env, config)
        manager.add_agent("trend_bot", AgentStrategy.TREND_FOLLOWING)
        manager.add_agent("rl_bot", AgentStrategy.RL_TRAINED, policy)
        results = manager.run_tournament()
    """

    def __init__(
        self,
        env: RLTradingEnvironment,
        config: Optional[SelfPlayConfig] = None,
    ):
        self.env = env
        self.config = config or SelfPlayConfig()
        self._agents: Dict[str, SelfPlayAgent] = {}
        self._rng = random.Random(self.config.seed)
        self._round_results: List[CompetitionResult] = []
        self._opponent_pool: List[PolicyNetwork] = []

    def add_agent(
        self,
        agent_id: str,
        strategy: AgentStrategy,
        policy: Optional[PolicyNetwork] = None,
        initial_elo: Optional[float] = None,
    ):
        """Add an agent to the self-play ecosystem."""
        agent = SelfPlayAgent(
            agent_id=agent_id,
            strategy=strategy,
            policy=policy,
            elo_rating=initial_elo or self.config.initial_elo,
        )
        self._agents[agent_id] = agent

    def remove_agent(self, agent_id: str):
        """Remove an agent from the ecosystem."""
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Optional[SelfPlayAgent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def run_tournament(self) -> List[CompetitionResult]:
        """Run full self-play tournament."""
        results = []

        for round_id in range(self.config.n_rounds):
            # Select opponents
            pairings = self._create_pairings()

            round_results = []
            for agent_a_id, agent_b_id in pairings:
                match_result = self._run_match(agent_a_id, agent_b_id)
                round_results.append(match_result)

            # Update ELO ratings
            self._update_elo_ratings(round_results)

            # Get rankings
            rankings = self._get_rankings()
            best_id = rankings[0][0] if rankings else ""
            best_score = rankings[0][1] if rankings else 0.0

            result = CompetitionResult(
                round_id=round_id,
                rankings=rankings,
                match_results=round_results,
                best_agent_id=best_id,
                best_score=best_score,
                elo_standings={aid: a.elo_rating for aid, a in self._agents.items()},
            )
            results.append(result)
            self._round_results.append(result)

            # Update opponent pool
            if self.config.use_opponent_pool:
                self._update_opponent_pool()

        return results

    def _create_pairings(self) -> List[Tuple[str, str]]:
        """Create match pairings for a round."""
        agent_ids = list(self._agents.keys())
        if len(agent_ids) < 2:
            return []

        self._rng.shuffle(agent_ids)
        pairings = []
        for i in range(0, len(agent_ids) - 1, 2):
            pairings.append((agent_ids[i], agent_ids[i + 1]))

        # Handle odd number
        if len(agent_ids) % 2 == 1:
            pairings.append((agent_ids[-1], agent_ids[0]))

        return pairings

    def _run_match(
        self, agent_a_id: str, agent_b_id: str
    ) -> Dict[str, Any]:
        """Run a match between two agents."""
        agent_a = self._agents[agent_a_id]
        agent_b = self._agents[agent_b_id]

        a_score = 0.0
        b_score = 0.0
        a_wins = 0
        b_wins = 0

        for ep in range(self.config.episodes_per_round):
            state = self.env.reset(seed=self.config.seed + ep)

            done = False
            a_ep_reward = 0.0
            b_ep_reward = 0.0

            while not done:
                # Agent A acts
                action_a = self._get_agent_action(agent_a, state)
                # Agent B acts
                action_b = self._get_agent_action(agent_b, state)

                # Combined action (average of both)
                combined_action = {}
                for symbol in self.env.config.symbols:
                    a_val = action_a.get(symbol, 0.0)
                    b_val = action_b.get(symbol, 0.0)
                    combined_action[symbol] = (a_val + b_val) / 2.0

                step = self.env.step(combined_action)
                a_ep_reward += step.reward
                b_ep_reward += step.reward

                done = step.done or step.truncated

            a_score += a_ep_reward
            b_score += b_ep_reward

            if a_ep_reward > b_ep_reward:
                a_wins += 1
            elif b_ep_reward > a_ep_reward:
                b_wins += 1

        return {
            "agent_a": agent_a_id,
            "agent_b": agent_b_id,
            "a_score": a_score,
            "b_score": b_score,
            "a_wins": a_wins,
            "b_wins": b_wins,
            "winner": agent_a_id if a_score > b_score else agent_b_id,
        }

    def _get_agent_action(
        self, agent: SelfPlayAgent, state: MarketState
    ) -> Dict[str, float]:
        """Get action from an agent based on its strategy."""
        symbols = self.env.config.symbols
        prices = state.prices

        if agent.strategy == AgentStrategy.RL_TRAINED and agent.policy:
            action_vec, _, _ = agent.policy.forward(
                state.to_vector(), deterministic=True
            )
            return {
                s: float(action_vec[i]) if i < len(action_vec) else 0.0
                for i, s in enumerate(symbols)
            }

        elif agent.strategy == AgentStrategy.TREND_FOLLOWING:
            # Buy if recent trend is positive
            return {
                s: 0.1 if state.returns.get(s, 0.0) > 0 else -0.05
                for s in symbols
            }

        elif agent.strategy == AgentStrategy.MEAN_REVERSION:
            # Buy if below moving average, sell if above
            return {
                s: -0.1 if state.returns.get(s, 0.0) > 0 else 0.1
                for s in symbols
            }

        elif agent.strategy == AgentStrategy.MARKET_MAKING:
            # Provide liquidity both sides
            return {
                s: self._rng.uniform(-0.05, 0.05)
                for s in symbols
            }

        elif agent.strategy == AgentStrategy.MOMENTUM:
            # Strong directional bets
            return {
                s: 0.2 if state.returns.get(s, 0.0) > 0.01 else -0.2
                for s in symbols
            }

        elif agent.strategy == AgentStrategy.BUY_HOLD:
            return {s: 0.1 for s in symbols}

        elif agent.strategy == AgentStrategy.RANDOM:
            return {
                s: self._rng.uniform(-0.1, 0.1)
                for s in symbols
            }

        else:
            return {s: 0.0 for s in symbols}

    def _update_elo_ratings(self, match_results: List[Dict[str, Any]]):
        """Update ELO ratings based on match results."""
        for match in match_results:
            a_id = match["agent_a"]
            b_id = match["agent_b"]
            agent_a = self._agents[a_id]
            agent_b = self._agents[b_id]

            # Expected scores
            expected_a = 1.0 / (1.0 + 10 ** ((agent_b.elo_rating - agent_a.elo_rating) / 400.0))
            expected_b = 1.0 - expected_a

            # Actual scores
            a_wins = match["a_wins"]
            b_wins = match["b_wins"]
            total_games = a_wins + b_wins
            actual_a = a_wins / total_games if total_games > 0 else 0.5
            actual_b = 1.0 - actual_a

            # Update ELO
            agent_a.elo_rating += self.config.elo_k_factor * (actual_a - expected_a)
            agent_b.elo_rating += self.config.elo_k_factor * (actual_b - expected_b)

            # Update win/loss
            agent_a.win_count += a_wins
            agent_a.loss_count += b_wins
            agent_b.win_count += b_wins
            agent_b.loss_count += a_wins

            agent_a.total_reward += match["a_score"]
            agent_b.total_reward += match["b_score"]

    def _get_rankings(self) -> List[Tuple[str, float, float]]:
        """Get agent rankings by ELO."""
        sorted_agents = sorted(
            self._agents.items(),
            key=lambda x: x[1].elo_rating,
            reverse=True,
        )
        return [
            (aid, agent.elo_rating, agent.win_rate())
            for aid, agent in sorted_agents
        ]

    def _update_opponent_pool(self):
        """Update opponent policy pool for robust training."""
        for agent in self._agents.values():
            if agent.policy is not None:
                self._opponent_pool.append(copy.deepcopy(agent.policy))

        # Keep pool size bounded
        if len(self._opponent_pool) > self.config.opponent_pool_size:
            self._opponent_pool = self._opponent_pool[
                -self.config.opponent_pool_size:
            ]

    def get_best_agent(self) -> Optional[SelfPlayAgent]:
        """Get the best performing agent."""
        if not self._agents:
            return None
        return max(self._agents.values(), key=lambda a: a.elo_rating)

    def get_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all agents."""
        return {
            aid: {
                "strategy": agent.strategy.value,
                "elo": agent.elo_rating,
                "wins": agent.win_count,
                "losses": agent.loss_count,
                "win_rate": agent.win_rate(),
                "total_reward": agent.total_reward,
            }
            for aid, agent in self._agents.items()
        }

    def get_elo_history(self) -> Dict[str, List[float]]:
        """Get ELO rating history for all agents."""
        history: Dict[str, List[float]] = {
            aid: [] for aid in self._agents
        }
        for result in self._round_results:
            for aid in self._agents:
                history[aid].append(result.elo_standings.get(aid, 1500.0))
        return history

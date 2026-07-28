"""Strategy Generator – auto-generate strategies from research goals."""

from typing import Any, Dict, List, Optional

from .genome import GenomeComponent, StrategyGenome


class StrategyGenerator:
    """Generates new strategies from research goals, market context, and factors.

    Can produce strategies from:
    - Predefined templates (momentum, mean reversion, breakout, etc.)
    - Factor-based assembly (combine factors into a strategy)
    - Research goals (natural language goal → strategy structure)
    - Random exploration (for genetic diversity)
    """

    # Available rule types per component category
    ENTRY_RULES = ["ma_cross", "bollinger_band", "price_channel", "rsi_signal",
                   "macd_signal", "volume_breakout", "support_resistance"]
    FILTER_RULES = ["volume", "rsi", "atr", "adx", "sentiment", "correlation",
                    "market_regime", "sector_momentum"]
    EXIT_RULES = ["atr_stop", "trailing_stop", "mean_return", "time_stop",
                  "target_pct", "signal_reverse", "volatility_stop"]
    RISK_RULES = ["fixed_pct", "volatility_adj", "kelly", "equal_weight",
                  "risk_parity"]

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._counter = 0

    # ------------------------------------------------------------------
    # Generation from templates
    # ------------------------------------------------------------------

    def generate(self, goal: str) -> dict:
        """Generate a strategy from a research goal (legacy interface).

        Returns a simple dict for backward compatibility.
        """
        genome = self.generate_from_goal(goal)
        return {"strategy": goal, "genome": genome.to_dict()}

    def generate_from_goal(self, goal: str) -> StrategyGenome:
        """Generate a strategy genome from a research goal description."""
        goal_lower = goal.lower()

        if "momentum" in goal_lower or "trend" in goal_lower:
            genome = StrategyGenome.create_momentum_template()
            genome.description = f"Auto-generated from goal: {goal}"
        elif "mean" in goal_lower or "reversion" in goal_lower or "reversal" in goal_lower:
            genome = StrategyGenome.create_mean_reversion_template()
            genome.description = f"Auto-generated from goal: {goal}"
        elif "breakout" in goal_lower:
            genome = StrategyGenome.create_breakout_template()
            genome.description = f"Auto-generated from goal: {goal}"
        else:
            # Default: create a custom strategy with the goal name
            genome = StrategyGenome(
                name=goal,
                description=f"Custom strategy generated from goal: {goal}",
                entry=GenomeComponent(
                    name="entry",
                    rule_type="ma_cross",
                    params={"fast_period": 10, "slow_period": 30},
                ),
                filters=[
                    GenomeComponent(
                        name="volume_filter",
                        rule_type="volume",
                        params={"min_volume_ratio": 1.2},
                    ),
                ],
                exit=GenomeComponent(
                    name="exit",
                    rule_type="trailing_stop",
                    params={"trail_pct": 3.0},
                ),
                risk=GenomeComponent(
                    name="risk",
                    rule_type="fixed_pct",
                    params={"max_risk_pct": 1.0},
                ),
            )

        genome.tags.append("auto_generated")
        return genome

    def generate_from_template(self, template_name: str) -> Optional[StrategyGenome]:
        """Generate from a named template."""
        templates = {
            "momentum": StrategyGenome.create_momentum_template,
            "mean_reversion": StrategyGenome.create_mean_reversion_template,
            "breakout": StrategyGenome.create_breakout_template,
        }
        factory = templates.get(template_name)
        if factory:
            genome = factory()
            genome.tags.append("template")
            return genome
        return None

    def generate_random(self, name_prefix: str = "RandomAlpha") -> StrategyGenome:
        """Generate a random strategy genome for exploration.

        Uses a deterministic pseudo-random approach based on the seed
        to ensure reproducibility.
        """
        self._counter += 1
        idx = (self._seed + self._counter) % 100

        entry_rule = self.ENTRY_RULES[idx % len(self.ENTRY_RULES)]
        filter_rule = self.FILTER_RULES[(idx + 1) % len(self.FILTER_RULES)]
        exit_rule = self.EXIT_RULES[(idx + 2) % len(self.EXIT_RULES)]
        risk_rule = self.RISK_RULES[(idx + 3) % len(self.RISK_RULES)]

        params_base = {
            "ma_cross": {"fast_period": 10 + idx % 40, "slow_period": 30 + idx % 60},
            "bollinger_band": {"period": 15 + idx % 10, "std_dev": 1.5 + (idx % 10) * 0.1},
            "price_channel": {"lookback": 10 + idx % 30, "breakout_pct": 0.01 + (idx % 10) * 0.005},
            "rsi_signal": {"oversold": 25 + idx % 15, "overbought": 65 + idx % 15},
            "atr_stop": {"atr_multiple": 1.5 + (idx % 10) * 0.3},
            "trailing_stop": {"trail_pct": 2.0 + (idx % 10) * 0.5},
            "fixed_pct": {"max_risk_pct": 1.0 + (idx % 10) * 0.3},
            "volatility_adj": {"base_risk_pct": 1.5 + (idx % 10) * 0.2},
        }

        genome = StrategyGenome(
            name=f"{name_prefix}_{self._counter}",
            description=f"Randomly generated exploration strategy #{self._counter}",
            entry=GenomeComponent(
                name="entry",
                rule_type=entry_rule,
                params=params_base.get(entry_rule, {}),
            ),
            filters=[
                GenomeComponent(
                    name=f"{filter_rule}_filter",
                    rule_type=filter_rule,
                    params=params_base.get(filter_rule, {"threshold": 0.5}),
                ),
            ],
            exit=GenomeComponent(
                name="exit",
                rule_type=exit_rule,
                params=params_base.get(exit_rule, {}),
            ),
            risk=GenomeComponent(
                name="risk",
                rule_type=risk_rule,
                params=params_base.get(risk_rule, {}),
            ),
            tags=["random_exploration"],
        )
        return genome

    def generate_batch(self, goal: str, count: int = 5) -> List[StrategyGenome]:
        """Generate multiple strategy variants from a single goal."""
        base = self.generate_from_goal(goal)
        variants = [base]

        for i in range(1, count):
            variant = StrategyGenome(
                name=f"{goal} v{i+1}",
                description=f"Variant {i+1} of: {goal}",
                entry=GenomeComponent(
                    name="entry",
                    rule_type=base.entry.rule_type,
                    params=dict(base.entry.params),
                ),
                filters=[GenomeComponent(
                    name=f.name,
                    rule_type=f.rule_type,
                    params=dict(f.params),
                ) for f in base.filters],
                exit=GenomeComponent(
                    name="exit",
                    rule_type=base.exit.rule_type,
                    params=dict(base.exit.params),
                ),
                risk=GenomeComponent(
                    name="risk",
                    rule_type=base.risk.rule_type,
                    params=dict(base.risk.params),
                ),
                generation=0,
                parent_ids=[base.name],
                tags=list(base.tags) + ["variant"],
            )
            variants.append(variant)

        return variants

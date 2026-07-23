"""
AI evolution center.
"""


class AIEvolutionCenter:

    def __init__(
        self,
        learning_engine,
        strategy_agent,
    ):

        self.learning_engine = learning_engine

        self.strategy_agent = strategy_agent

    def evolve(
        self,
        experience,
        strategy,
        performance,
    ):

        self.learning_engine.learn(
            experience
        )

        return self.strategy_agent.evaluate(
            strategy,
            performance,
        )
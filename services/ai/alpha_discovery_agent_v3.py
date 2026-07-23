"""
Alpha Discovery Agent v3.
"""


class AlphaDiscoveryAgentV3:

    def __init__(
        self,
        mining_engine,
        ai_service,
    ):

        self.mining_engine = mining_engine

        self.ai_service = ai_service

    def discover(
        self,
        objective,
    ):

        factors = self.mining_engine.mine(
            objective
        )

        return self.ai_service.execute(
            str(factors)
        )
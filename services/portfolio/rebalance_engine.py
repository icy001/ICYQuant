"""
Portfolio rebalance engine.
"""

from .rebalance import RebalanceRequest


class RebalanceEngine:
    def __init__(
        self,
        detector,
        policy,
    ):
        self.detector = detector
        self.policy = policy

    def evaluate(
        self,
        current,
        target,
    ):
        requests = []

        for asset, target_weight in target.items():
            current_weight = current.get(asset, 0)
            drift = self.detector.calculate(current_weight, target_weight)

            if self.detector.exceed_threshold(drift, self.policy.threshold):
                requests.append(
                    RebalanceRequest(
                        asset=asset,
                        current_weight=current_weight,
                        target_weight=target_weight,
                        delta=drift,
                    )
                )

        return requests
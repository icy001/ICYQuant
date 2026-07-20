"""
Asset allocation engine.
"""

from .allocation_snapshot import AllocationSnapshot


class AssetAllocationEngine:
    def __init__(
        self,
        validator,
        rebalance,
    ):
        self.validator = validator
        self.rebalance = rebalance

    def allocate(
        self,
        targets,
        current,
    ):
        if not self.validator.validate(targets):
            raise ValueError("invalid allocation")

        snapshots = []

        for target in targets:
            current_weight = current.get(target.asset_class, 0)

            snapshots.append(
                AllocationSnapshot(
                    asset_class=target.asset_class,
                    current_weight=current_weight,
                    target_weight=target.target_weight,
                )
            )

        return snapshots
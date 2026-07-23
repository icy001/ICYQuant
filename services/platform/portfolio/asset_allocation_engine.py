"""
Asset allocation engine.
"""


class AssetAllocationEngine:

    def allocate(
        self,
        assets,
        constraints,
    ):

        return {
            "allocation": assets,
            "constraints": constraints,
        }
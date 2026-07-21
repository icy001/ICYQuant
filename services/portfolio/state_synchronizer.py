"""
State synchronizer.
"""


class StateSynchronizer:

    def synchronize(
        self,
        source,
        target,
    ):

        target.data.update(
            source.data
        )

        return target
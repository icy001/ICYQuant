"""
Rolling window splitter.
"""


class RollingWindowSplitter:
    def split(
        self,
        dataset,
        window_size,
    ):
        return [
            dataset[:window_size],
            dataset[window_size:]
        ]
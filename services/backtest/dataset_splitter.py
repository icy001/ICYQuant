"""
Training / testing splitter.
"""


class DatasetSplitter:

    def split(
        self,
        data,
        train_size,
    ):

        split_index = int(
            len(data) * train_size
        )

        return (
            data[:split_index],
            data[split_index:],
        )
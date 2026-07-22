"""
Metadata catalog.
"""


class MetadataCatalog:

    def __init__(self):

        self._metadata = {}

    def register(
        self,
        dataset,
        metadata,
    ):

        self._metadata[dataset] = metadata

    def get(
        self,
        dataset,
    ):

        return self._metadata.get(
            dataset,
        )
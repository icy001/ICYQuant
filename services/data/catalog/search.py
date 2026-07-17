"""
Metadata search engine.
"""


class MetadataSearch:
    def search(
        self,
        datasets,
        keyword,
    ):
        return [
            item
            for item in datasets
            if keyword.lower() in item.name.lower()
        ]
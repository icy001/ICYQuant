"""
Catalog service.
"""


class CatalogService:
    def __init__(
        self,
        catalog,
        search,
    ):
        self.catalog = catalog
        self.search = search

    def discover(
        self,
        keyword,
    ):
        return self.search.search(
            self.catalog.list_all(),
            keyword,
        )
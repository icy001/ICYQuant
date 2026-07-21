"""
Materialized view.
"""


class MaterializedView:

    def refresh(
        self,
        projection,
    ):

        return projection.data
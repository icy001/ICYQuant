"""
Parameter comparator.
"""

from .snapshot import ParameterSnapshot


class ParameterComparator:
    def compare(
        self,
        left: ParameterSnapshot,
        right: ParameterSnapshot,
    ):
        return {
            "same": left.group == right.group,
            "left": left.version,
            "right": right.version,
        }
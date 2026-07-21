"""
Portfolio version diff.
"""


class VersionDiff:
    def compare(
        self,
        old,
        new,
    ):
        diff = {}

        keys = set(old) | set(new)

        for key in keys:
            if old.get(key) != new.get(key):
                diff[key] = {
                    "before": old.get(key),
                    "after": new.get(key),
                }

        return diff
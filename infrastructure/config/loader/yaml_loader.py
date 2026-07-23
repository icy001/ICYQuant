"""
YAML configuration loader.
"""


class YAMLLoader:

    def load(
        self,
        source,
    ):
        return {
            "source":
                source,
            "loaded":
                True
        }
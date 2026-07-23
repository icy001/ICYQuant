"""
AI context builder.
"""


class ContextBuilder:

    def build(
        self,
        memories,
    ):

        return "\n".join(
            memories
        )
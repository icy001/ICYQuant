"""
AI service foundation.
"""


class AIService:

    def __init__(
        self,
        provider,
    ):

        self.provider = provider

    def execute(
        self,
        prompt,
    ):

        return self.provider.generate(
            prompt
        )
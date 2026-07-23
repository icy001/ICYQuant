"""
Prompt service layer.
"""


class PromptService:

    def __init__(
        self,
        engine,
        registry,
    ):

        self.engine = engine

        self.registry = registry

    def build(
        self,
        prompt_id,
        variables,
    ):

        template = self.registry.get(
            prompt_id,
        )

        return self.engine.render(
            template,
            variables,
        )
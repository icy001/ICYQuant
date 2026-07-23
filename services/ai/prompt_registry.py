"""
Prompt registry.
"""


class PromptRegistry:

    def __init__(self):

        self._templates = {}

    def register(
        self,
        template,
    ):

        self._templates[
            template.template_id
        ] = template

    def get(
        self,
        template_id,
    ):

        return self._templates.get(
            template_id,
        )
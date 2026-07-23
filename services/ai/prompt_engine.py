"""
Prompt template engine.
"""


class PromptEngine:

    def render(
        self,
        template,
        variables,
    ):

        content = template.content

        for key, value in variables.items():

            content = content.replace(
                "{{" + key + "}}",
                str(value),
            )

        return content
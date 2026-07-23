"""
AI quantitative research pipeline.
"""


class ResearchPipeline:

    def __init__(
        self,
        alpha_agent,
        notebook,
    ):

        self.alpha_agent = alpha_agent

        self.notebook = notebook

    def execute(
        self,
        objective,
    ):

        result = self.alpha_agent.research(
            objective
        )

        self.notebook.add(
            objective,
            result,
        )

        return result
"""
Research intelligence center.
"""


class ResearchIntelligenceCenter:

    def __init__(
        self,
        analyst,
        alpha_engine,
        generator,
    ):

        self.analyst = analyst

        self.alpha = alpha_engine

        self.generator = generator

    def research(
        self,
        company,
        data,
    ):

        analysis = self.analyst.analyze(
            company,
            data,
        )

        alpha = self.alpha.discover(
            analysis
        )

        return self.generator.generate(
            company,
            alpha,
        )
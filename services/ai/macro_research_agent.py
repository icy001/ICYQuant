"""
Macro research intelligence agent.
"""


class MacroResearchAgent:

    def __init__(
        self,
        macro_service,
        ai_service,
    ):

        self.macro_service = macro_service

        self.ai_service = ai_service

    def analyze(
        self,
        region,
    ):

        macro = self.macro_service.get(
            region
        )

        return self.ai_service.execute(
            str(macro)
        )
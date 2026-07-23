"""
AI Trading Agent.
"""


class TradingAgent:

    def __init__(
        self,
        ai_service,
        context_service,
    ):

        self.ai_service = ai_service

        self.context_service = context_service

    def analyze(
        self,
        symbol,
    ):

        context = self.context_service.build_context(
            symbol
        )

        prompt = f"""
        Analyze trading opportunity:
        Symbol:
        {symbol}
        Context:
        {context}
        """

        return self.ai_service.execute(
            prompt
        )
"""
News intelligence agent.
"""


class NewsAnalysisAgent:

    def __init__(
        self,
        news_service,
        ai_service,
    ):

        self.news_service = news_service

        self.ai_service = ai_service

    def analyze(
        self,
        symbols,
    ):

        news = self.news_service.query(
            symbols
        )

        return self.ai_service.execute(
            str(news)
        )
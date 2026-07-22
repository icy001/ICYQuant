"""
Order risk pipeline.
"""


class OrderRiskPipeline:

    def __init__(
        self,
        service,
    ):

        self.service = service

    def process(
        self,
        request,
    ):

        return self.service.execute(
            request,
        )
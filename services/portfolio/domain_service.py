"""
Portfolio domain service.
"""


class PortfolioDomainService:

    def __init__(
        self,
        facade,
    ):

        self.facade = facade

    def module(
        self,
        name,
    ):

        return self.facade.service(
            name,
        )
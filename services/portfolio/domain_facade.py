"""
Portfolio domain facade.
"""


class PortfolioDomainFacade:

    def __init__(
        self,
        services,
    ):

        self.services = services

    def service(
        self,
        name,
    ):

        return self.services[name]
"""
Structured logger.
"""


class PortfolioLogger:

    def info(
        self,
        message,
        **fields,
    ):

        return {
            "level": "INFO",
            "message": message,
            **fields,
        }
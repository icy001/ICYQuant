"""
Strategy exceptions.
"""


class StrategyError(Exception):
    """Base strategy exception."""


class StrategyStoppedError(StrategyError):
    """Strategy is not running."""
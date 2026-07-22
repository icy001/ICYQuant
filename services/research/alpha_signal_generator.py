"""
Alpha signal generator.
"""

from .alpha_signal import AlphaSignal


class AlphaSignalGenerator:

    def generate(
        self,
        alpha,
        symbol,
        score,
        timestamp,
    ):

        return AlphaSignal(
            alpha_id=alpha.alpha_id,
            symbol=symbol,
            score=score,
            timestamp=timestamp,
        )
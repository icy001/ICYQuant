"""
Market regime detection.
"""


class MarketRegimeDetector:

    def detect(
        self,
        market_data,
    ):

        return {
            "regime": "normal",
            "confidence": 0.5,
        }
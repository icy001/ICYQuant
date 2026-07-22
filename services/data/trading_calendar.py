"""
Trading calendar.
"""

from datetime import date


class TradingCalendar:

    def is_trading_day(
        self,
        trading_date: date,
    ):

        return trading_date.weekday() < 5
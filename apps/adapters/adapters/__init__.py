"""Market adapters (A-Share / Futures / US Equity / FX)."""

from apps.adapters.adapters.ashare import AshareAdapter
from apps.adapters.adapters.futures import FuturesAdapter
from apps.adapters.adapters.fx import FxAdapter
from apps.adapters.adapters.us_equity import UsEquityAdapter

__all__ = ["AshareAdapter", "FuturesAdapter", "UsEquityAdapter", "FxAdapter"]

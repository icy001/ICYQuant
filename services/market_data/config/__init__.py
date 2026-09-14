"""Market data configuration package (Commit 014 §4).

Non-secret, environment-driven settings for the broker market data
adapter live here.  Credentials (account / password / token) are read
from the environment at wiring time and are **never** written into the
source tree.

Import surface::

    from services.market_data.config import BrokerMarketDataConfig

    config = BrokerMarketDataConfig.from_env()
"""
from __future__ import annotations

from .broker_config import BrokerMarketDataConfig

__all__ = ["BrokerMarketDataConfig"]

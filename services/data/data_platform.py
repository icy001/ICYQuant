"""
Institutional Data Platform Facade.
"""

from .data_service import DataService
from .historical_service import HistoricalService
from .realtime_market_data_service import RealtimeMarketDataService
from .feature_retrieval_service import FeatureRetrievalService
from .cache_service import CacheService


class DataPlatform:

    def __init__(
        self,
        market_data: DataService,
        historical: HistoricalService,
        realtime: RealtimeMarketDataService,
        feature: FeatureRetrievalService,
        cache: CacheService,
    ):

        self.market_data = market_data

        self.historical = historical

        self.realtime = realtime

        self.feature = feature

        self.cache = cache
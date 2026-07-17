from services.data.marketplace import (
    UsageTracker,
    DatasetListing,
    DatasetSubscription,
    SharingRequest,
    DatasetRating,
    MarketplaceService,
)


def test_dataset_usage():
    tracker = UsageTracker()

    tracker.record("NVDA_DATA")

    assert tracker.usage("NVDA_DATA") == 1


def test_dataset_usage_multiple():
    tracker = UsageTracker()

    tracker.record("NASDAQ_DATA")
    tracker.record("NASDAQ_DATA")
    tracker.record("NYSE_DATA")

    assert tracker.usage("NASDAQ_DATA") == 2
    assert tracker.usage("NYSE_DATA") == 1


def test_dataset_listing():
    listing = DatasetListing(
        dataset="US_EQUITY_TICK",
        publisher="Market Data Team",
        description="US equity tick data",
    )

    assert listing.dataset == "US_EQUITY_TICK"
    assert listing.publisher == "Market Data Team"
    assert listing.status == "PUBLISHED"


def test_dataset_subscription():
    subscription = DatasetSubscription(user="Quant_A", dataset="NASDAQ_TICK_DATA")

    assert subscription.user == "Quant_A"
    assert subscription.dataset == "NASDAQ_TICK_DATA"
    assert subscription.status == "ACTIVE"


def test_sharing_request():
    request = SharingRequest(
        owner="DataOwner",
        receiver="Quant_B",
        dataset="PRIVATE_DATA",
    )

    assert request.owner == "DataOwner"
    assert request.receiver == "Quant_B"
    assert request.status == "PENDING"


def test_dataset_rating():
    rating = DatasetRating(dataset="SP500_FEATURE", score=4.8, reviewer="Quant_C")

    assert rating.dataset == "SP500_FEATURE"
    assert rating.score == 4.8
    assert rating.reviewer == "Quant_C"


def test_marketplace_service():
    tracker = UsageTracker()
    service = MarketplaceService(tracker)

    service.subscribe("FOREX_DATA")

    assert tracker.usage("FOREX_DATA") == 1
from services.feature_flag import *


def test_feature_flag():

    service = FeatureFlagService(
        FeatureRepository(),
        RuleEvaluator()
    )

    feature = Feature(
        "FF001",
        "NEW_RISK_ENGINE",
        True
    )

    service.register(feature)

    assert service.is_enabled("FF001")

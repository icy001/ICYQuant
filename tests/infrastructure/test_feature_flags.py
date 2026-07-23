from infrastructure.feature_flags import (
    FeatureFlag,
    FeatureStorage,
    FeatureEvaluator,
    FeatureManager,
)


def test_feature_flag():

    storage = FeatureStorage()

    storage.save(

        FeatureFlag(

            "new-alpha",

            True,

            "new strategy"

        )

    )


    manager = FeatureManager(

        storage,

        FeatureEvaluator()

    )


    assert manager.enabled(

        "new-alpha"

    )
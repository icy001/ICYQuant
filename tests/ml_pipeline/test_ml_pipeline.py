from services.ml_pipeline import *


def test_ml_pipeline():

    registry = ModelRegistry()

    service = MLService(
        registry
    )

    service.register_model(

        "MomentumModel",

        "v1"

    )

    model = service.get_model(
        "MomentumModel"
    )

    assert model == "v1"

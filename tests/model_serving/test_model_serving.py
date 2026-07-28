from services.model_serving import *


class MockModel:

    def predict(self, features):

        return 0.8


def test_serving():

    deployment = DeploymentManager()

    deployment.deploy(
        "MomentumModel",
        MockModel()
    )

    service = ModelServingService(
        deployment
    )

    result = service.predict(

        "MomentumModel",

        {}

    )

    assert result == 0.8

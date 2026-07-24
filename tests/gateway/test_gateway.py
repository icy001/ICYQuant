from services.gateway import *


def test_gateway_route():


    router = Router()


    router.register(

        "/health",

        lambda req: {

            "ok": True

        }

    )


    gateway = APIGateway(

        router,

        MiddlewareChain()

    )


    response = gateway.handle(

        Request(

            "/health",

            "GET",

            {},

            {}

        )

    )


    assert response.status_code == 200
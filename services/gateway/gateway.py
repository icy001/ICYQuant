from .response import Response


class APIGateway:


    def __init__(

        self,

        router,

        middleware,

    ):

        self.router = router

        self.middleware = middleware



    def handle(

        self,

        request,

    ):

        request = self.middleware.execute(

            request

        )


        result = self.router.dispatch(

            request.path,

            request

        )


        return Response(

            200,

            result

        )
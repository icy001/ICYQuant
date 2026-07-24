class Router:


    def __init__(self):

        self.routes = {}



    def register(

        self,

        path,

        handler,

    ):

        self.routes[path] = handler



    def dispatch(

        self,

        path,

        request,

    ):

        handler = self.routes.get(path)


        if not handler:

            raise Exception(

                "Route not found"

            )


        return handler(request)
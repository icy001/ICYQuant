class MiddlewareChain:


    def __init__(self):

        self.middlewares = []



    def add(

        self,

        middleware,

    ):

        self.middlewares.append(

            middleware

        )



    def execute(

        self,

        request,

    ):

        for middleware in self.middlewares:

            middleware.handle(request)


        return request
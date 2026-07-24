class ShutdownManager:


    def __init__(self):

        self.handlers = []



    def register(

        self,

        handler,

    ):

        self.handlers.append(handler)



    def shutdown(self):

        for handler in self.handlers:

            handler()
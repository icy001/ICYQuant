class Provider:


    def __init__(

        self,

        factory,

    ):

        self.factory = factory

        self.instance = None



    def create(self):

        if self.instance:

            return self.instance


        self.instance = self.factory()

        return self.instance
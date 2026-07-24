class Resolver:


    def __init__(

        self,

        container,

    ):

        self.container = container



    def inject(

        self,

        dependency,

    ):

        return self.container.resolve(

            dependency

        )
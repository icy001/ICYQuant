class DependencyContainer:


    def __init__(self):

        self.providers = {}



    def register(

        self,

        name,

        provider,

    ):

        self.providers[name] = provider



    def resolve(

        self,

        name,

    ):

        provider = self.providers.get(name)

        if not provider:

            raise Exception(

                "Dependency missing"

            )

        return provider.create()
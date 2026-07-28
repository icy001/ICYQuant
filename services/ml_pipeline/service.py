class MLService:

    def __init__(self, registry):

        self.registry = registry

    def register_model(self, name, model):

        self.registry.register(
            name,
            model
        )

    def get_model(self, name):

        return self.registry.get(name)

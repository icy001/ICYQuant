class ConfigurationManager:


    def __init__(

        self,

        registry,

        validator,

    ):

        self.registry = registry

        self.validator = validator



    def update(

        self,

        config,

    ):

        if self.validator.validate(config):

            self.registry.register(config)

            return True


        return False
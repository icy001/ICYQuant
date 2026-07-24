class ConfigRegistry:


    def __init__(self):

        self.configs = {}



    def register(

        self,

        config,

    ):

        self.configs[config.name] = config



    def get(

        self,

        name,

    ):

        return self.configs.get(name)
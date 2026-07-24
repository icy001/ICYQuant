class RuntimeContainer:


    def __init__(self):

        self.services = {}



    def register(

        self,

        service,

    ):

        self.services[service.name] = service



    def get(

        self,

        name,

    ):

        return self.services.get(name)
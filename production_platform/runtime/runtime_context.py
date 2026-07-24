class RuntimeContext:


    def __init__(self):

        self.attributes = {}



    def set(

        self,

        key,

        value,

    ):

        self.attributes[key] = value



    def get(

        self,

        key,

    ):

        return self.attributes.get(key)
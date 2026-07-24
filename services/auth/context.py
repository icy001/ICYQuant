class AuthContext:


    def __init__(self):

        self.identity = None



    def set_identity(

        self,

        identity,

    ):

        self.identity = identity



    def current(self):

        return self.identity
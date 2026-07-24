class TTLPolicy:

    def __init__(

        self,

        ttl=300,

    ):

        self.ttl = ttl

    def expired(

        self,

        age,

    ):

        return age > self.ttl
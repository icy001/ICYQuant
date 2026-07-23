class AccessPolicy:

    def allow(

        self,

        role,

    ):

        return role in (

            "admin",

            "service",

        )
class PermissionResolver:


    permissions = {


        "admin": [

            "*"

        ],


        "trader": [

            "order.create",

            "order.cancel"

        ],


        "viewer": [

            "portfolio.read"

        ]

    }



    def check(

        self,

        role,

        permission,

    ):

        allowed = self.permissions.get(

            role,

            []

        )


        return (

            "*"

            in allowed

            or

            permission

            in allowed

        )
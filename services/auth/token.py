import time


class TokenService:


    def generate(

        self,

        identity,

    ):

        return {

            "user_id": identity.user_id,

            "username": identity.username,

            "role": identity.role,

            "issued_at": time.time()

        }



    def validate(

        self,

        token,

    ):

        return token is not None
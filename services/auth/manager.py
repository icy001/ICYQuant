class AuthenticationManager:


    def __init__(

        self,

        token_service,

        session_manager,

    ):

        self.token_service = token_service

        self.session_manager = session_manager



    def login(

        self,

        identity,

    ):

        token = self.token_service.generate(

            identity

        )


        self.session_manager.create(

            identity.user_id,

            token

        )


        return token
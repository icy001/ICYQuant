class UserService:


    def __init__(

        self,

        manager,

    ):

        self.manager = manager



    def register(

        self,

        user,

    ):

        return self.manager.create(user)



    def profile(

        self,

        user_id,

    ):

        return self.manager.get(user_id)
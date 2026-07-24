class UserManager:


    def __init__(

        self,

        repository,

    ):

        self.repository = repository



    def create(

        self,

        user,

    ):

        self.repository.save(user)

        return user



    def get(

        self,

        user_id,

    ):

        return self.repository.find(user_id)
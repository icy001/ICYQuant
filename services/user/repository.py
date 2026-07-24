class UserRepository:


    def __init__(self):

        self.users = {}



    def save(

        self,

        user,

    ):

        self.users[user.user_id] = user



    def find(

        self,

        user_id,

    ):

        return self.users.get(user_id)
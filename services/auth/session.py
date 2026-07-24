class SessionManager:


    def __init__(self):

        self.sessions = {}



    def create(

        self,

        user_id,

        token,

    ):

        self.sessions[user_id] = token



    def get(

        self,

        user_id,

    ):

        return self.sessions.get(user_id)
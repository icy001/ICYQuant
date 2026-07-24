class LeaderElection:


    def __init__(self):

        self.leader = None



    def acquire(

        self,

        node,

    ):

        self.leader = node



    def is_leader(

        self,

        node,

    ):

        return self.leader == node
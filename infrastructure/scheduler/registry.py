class JobRegistry:


    def __init__(self):

        self.jobs = {}



    def register(

        self,

        job,

    ):

        self.jobs[job.name] = job



    def get(

        self,

        name,

    ):

        return self.jobs.get(name)
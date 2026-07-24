class Scheduler:


    def __init__(self):

        self.queue = []



    def submit(

        self,

        job,

    ):

        self.queue.append(job)



    def pending(self):

        return self.queue
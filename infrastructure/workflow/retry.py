class WorkflowRetry:


    def __init__(

        self,

        attempts=3,

    ):

        self.attempts = attempts



    def can_retry(

        self,

        count,

    ):

        return count < self.attempts
class BackoffStrategy:


    def delay(

        self,

        attempt,

    ):

        return attempt * 2
class SignalRanking:

    def rank(self, signals):

        return sorted(

            signals,

            key=lambda x: x.score,

            reverse=True

        )

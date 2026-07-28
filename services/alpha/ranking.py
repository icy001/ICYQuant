class FactorRanking:

    def rank(self, factors):

        return sorted(

            factors,

            key=lambda x: x.score,

            reverse=True

        )

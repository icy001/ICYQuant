class SignalScore:

    def calculate(self, factors):

        if not factors:

            return 0

        return sum(factors) / len(factors)

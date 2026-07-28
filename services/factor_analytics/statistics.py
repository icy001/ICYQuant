class ICStatistics:

    def calculate(self, values):

        if not values:

            return 0

        return sum(values) / len(values)

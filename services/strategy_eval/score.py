class StrategyScore:

    def calculate(self, metrics):

        return (

            metrics.return_rate +

            metrics.win_rate

        )

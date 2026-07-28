class AllocationEngine:

    def allocate(self, signals):

        return {

            signal: 1 / len(signals)

            for signal in signals

        }

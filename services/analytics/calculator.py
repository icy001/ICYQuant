class PerformanceCalculator:
    def calculate_return(self, initial, final):
        if initial == 0:
            return 0

        return (final - initial) / initial
from .result import ComplianceResult


class ComplianceEngine:
    def check(self, restriction):
        if restriction.restricted:
            return ComplianceResult(
                False,
                restriction.reason
            )
        return ComplianceResult(True)
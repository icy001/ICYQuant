"""
Institutional audit platform.
"""


class InstitutionalAuditPlatform:

    def __init__(
        self,
        auditor,
        compliance,
    ):
        self.auditor = auditor
        self.compliance = compliance

    def review(
        self,
        action,
    ):
        compliance = self.compliance.check(
            action
        )
        audit = self.auditor.audit()

        return {
            "compliance":
                compliance,
            "audit":
                audit
        }
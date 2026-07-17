"""
Approval workflow.
"""


class ApprovalWorkflow:
    def approve(
        self,
        request,
    ):
        return request.__class__(
            user=request.user,
            dataset=request.dataset,
            reason=request.reason,
            status="APPROVED",
        )
from fastapi import APIRouter

from services.reconciliation.application.service import ReconciliationApplicationService

router = APIRouter(prefix="/api/v1")

service = ReconciliationApplicationService()


@router.get("/health")
def health():
    return {
        "service": "ICYQuant",
        "version": "0.2.4",
        "status": "running",
    }


@router.post("/reconciliation/run")
def run_reconciliation(
    ledger_data: dict,
    position_data: dict,
    events: list = None,
):
    result = service.run_reconciliation(ledger_data, position_data, events)
    return result


@router.post("/reconciliation/repair")
def repair(reconciliation_result: dict):
    return service.repair(reconciliation_result)

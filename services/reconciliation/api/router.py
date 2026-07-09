from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {
        "service": "reconciliation",
        "version": "0.2.4-alpha1",
    }

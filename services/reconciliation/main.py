from fastapi import FastAPI

from .api.router import router
from .config import ReconciliationSettings

settings = ReconciliationSettings()

app = FastAPI(
    title=f"{settings.service_name.title()} Service",
    version=settings.version,
)

app.include_router(router)

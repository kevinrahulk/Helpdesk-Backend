from fastapi import APIRouter

from app.routers.reports.metrics import router as metrics_router
from app.routers.reports.export import router as export_router

router = APIRouter(prefix="/reports", tags=["Reports"])

router.include_router(metrics_router)
router.include_router(export_router)

"""Composed root routers for the Phase 10 service."""

from fastapi import APIRouter

from .analysis import router as analysis_router
from .anomalies import router as anomaly_router
from .evaluation import router as evaluation_router
from .health import router as health_router
from .metrics import router as metrics_router

api_router = APIRouter()
api_router.include_router(analysis_router)
api_router.include_router(anomaly_router)
api_router.include_router(evaluation_router)
api_router.include_router(metrics_router)

__all__ = ["api_router", "health_router"]
